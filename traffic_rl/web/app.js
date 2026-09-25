(() => {
  'use strict';
  const data=window.TRAFFIC_REPLAY, $=id=>document.getElementById(id);
  if(!data?.runs?.length||!data.layouts?.length){$('error').hidden=false;$('error').textContent='这份记录缺少学习数据。请使用新版 show 命令重新导出，保留完整文件夹。';return;}
  const layoutNames={intersection:'直行十字路口',crossroads:'转弯十字路口',tjunction:'丁字路口',roundabout:'入口受控环岛'};
  const scenarioNames={balanced:'均衡车流',peak:'高峰车流',tidal:'潮汐车流',surge:'突发车流'};
  const policyNames={fixed:'固定配时',queue:'排队优先',yield:'自然让行',dqn:'DQN 策略'};
  const notes={fixed:'按预设时长轮流放行，遵守信号时长约束。',queue:'优先服务排队较多的方向，仍受最小、最大绿灯约束。',yield:'入口持续开放，驶入车辆向环内车辆让行。',dqn:'加载已有模型进行确定性评估，回放期间不更新参数。'};
  const reasons={hold:'保持当前放行方向。',switch:'执行方向切换，并经过信号过渡。',min_green:'最小绿灯尚未满足，请求切换被暂缓，保持原方向。',max_green:'最长绿灯保护触发，控制器强制切换方向。',invalid:'请求的进口不存在，保持原方向并计入无效动作惩罚。',unmetered:'入口全部开放，信号不限制进入；环岛合流处仍按环内优先让行。'};
  const concepts={state:['状态 sₜ','智能体在决策时看到的数值。这里包括排队、密度、放行相位等。中文表格帮助理解路况，展开向量可查看实际输入模型的归一化数值。'],action:['动作 aₜ','策略希望放行的方向。旧路口有南北/东西两种动作，新道路有北/南/东/西四种。控制器还会检查最小绿灯、最长绿灯和进口是否存在，因此请求不一定原样执行。'],reward:['奖励 rₜ','执行动作后，环境计算的反馈分数。本例以停车车辆数的负值为主，加上配置的惩罚项。DQN 训练旨在提高累积折扣回报，而不是只追求某一步的最高分。'],episode:['回合 Episode','一次从仿真开始到设定时长结束的完整运行，包含多次决策。训练会经历多个回合并更新参数；此页面只回放已记录的评估回合。']};
  let run=data.runs[0],scene=data.layouts.find(s=>s.id===run.layout),t=0,playing=false,learning=false,speed=1,last=null,lastFrame=-1,lastDecision=-2;
  let fpsStart=null,fpsFrames=0,noticeTimer=null;
  const renderer=new window.TrafficRenderer($('map'));
  const clock=s=>`${Math.floor(s/60).toString().padStart(2,'0')}:${Math.floor(s%60).toString().padStart(2,'0')}`;
  const fmt=v=>Number(v).toFixed(2).replace(/\.00$/,'');
  const direction=d=>({N:'北',S:'南',E:'东',W:'西'}[d]);
  const actionName=a=>run.layout==='intersection'?['南北放行','东西放行'][a]:['北进口放行','南进口放行','东进口放行','西进口放行'][a];
  function options(select,values,names,preferred){select.replaceChildren(...values.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=names[v];return o;}));select.value=values.includes(preferred)?preferred:values[0];}
  function notify(message){$('notice').hidden=false;$('notice').textContent=message;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').hidden=true,5000);}
  function setPlaying(value){playing=value;last=null;$('play').textContent=value?'Ⅱ 暂停':'▶ 播放';$('state-label').textContent=value?'正在回放':t>=data.duration?'回放结束':'已暂停';}
  function scenariosForLayout(){return [...new Set(data.runs.filter(r=>r.layout===$('layout').value).map(r=>r.scenario))];}
  let scenario=run.scenario;
  function rebuildScenarios(){const values=scenariosForLayout();if(!values.includes(scenario))scenario=values[0];$('scenarios').replaceChildren(...values.map(s=>{const b=document.createElement('button');b.textContent=scenarioNames[s];b.classList.toggle('active',s===scenario);b.onclick=()=>{scenario=s;rebuildScenarios();chooseRun(true);};return b;}));}
  function chooseRun(reset){
    const previous=$('policy').value, candidates=data.runs.filter(r=>r.layout===$('layout').value&&r.scenario===scenario);
    options($('policy'),candidates.map(r=>r.policy),policyNames,previous);
    run=candidates.find(r=>r.policy===$('policy').value);
    if(previous&&previous!==run.policy)notify('当前组合没有该策略记录，已切换为'+policyNames[run.policy]+'。');
    scene=data.layouts.find(s=>s.id===run.layout);renderer.setScene(scene);
    if(reset){t=0;setPlaying(false);}
    $('map-title').textContent=layoutNames[run.layout];$('map-subtitle').textContent=run.layout==='roundabout'?' / 单车道 · 逆时针':' / SUMO 实际路网';
    $('seed').textContent=`SEED ${data.seed} · ${data.duration} 秒`;
    $('policy-title').textContent=policyNames[run.policy];$('policy-note').textContent=notes[run.policy]+(run.policy==='dqn'?' '+(run.modelNote||data.modelNote||'训练程度未知。'):'');
    $('run-description').textContent=`${layoutNames[run.layout]} · ${scenarioNames[run.scenario]} · ${policyNames[run.policy]} · ${run.planned} 辆计划到达`;
    $('final-wait').replaceChildren(document.createTextNode(run.metrics.mean_wait_plus_entry_delay_all_s.toFixed(1)));const unit=document.createElement('small');unit.textContent='秒';$('final-wait').append(unit);
    $('completion-rate').textContent=(run.metrics.completion_rate*100).toFixed(1)+'%';
    lastFrame=-1;lastDecision=-2;updateInfo();
  }
  function updateInfo(){
    const items=[['道路',layoutNames[run.layout]],['车流',scenarioNames[run.scenario]],['策略',policyNames[run.policy]],['模型',run.policy==='dqn'?(run.modelNote||data.modelNote||'训练程度未知'):'规则基线，无模型参数更新'],['随机种子',data.seed],['回合长度',data.duration+' 秒'],['决策周期',data.simulation.delta_time+' 秒'],['物理步长',data.simulation.step_length+' 秒'],['绿灯范围',`${data.simulation.min_green}–${data.simulation.max_green} 秒`],['黄灯',data.simulation.yellow_time+' 秒'],['全红',run.layout==='intersection'?'旧布局无全红':(data.simulation.delta_time-data.simulation.yellow_time)+' 秒'],['奖励范围',run.rewardScope],['到达文件 SHA256',run.demandHash],['状态维度',run.observationLabels.length],['数据来源','合成车流，未实地校准']];
    $('experiment-info').replaceChildren(...items.flatMap(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;return [dt,dd];}));
  }
  function setMode(value){learning=value;document.body.classList.toggle("learning-mode",value);setPlaying(false);$('learning').hidden=!value;$('step-controls').hidden=!value;$('demo-mode').classList.toggle('active',!value);$('learn-mode').classList.toggle('active',value);$('demo-mode').setAttribute('aria-pressed',!value);$('learn-mode').setAttribute('aria-pressed',value);$('page-title').textContent=value?'逐步理解一次强化学习决策。':'从一次放行，看懂交通决策。';$('mode-note').textContent=value?'按决策步查看真实状态、请求动作、执行约束和奖励。回放不会训练模型。':'选择道路与车流，观察不同控制策略如何影响车辆等待。';lastDecision=-2;}
  // At a boundary show the just-completed transition; never present future rewards as observed.
  function completedDecision(){let low=0,high=run.decisions.length;while(low<high){const m=(low+high)>>1;if(run.decisions[m].end<=t+1e-7)low=m+1;else high=m;}return low-1;}
  function step(delta){setPlaying(false);const ends=[0,...run.decisions.map(d=>d.end)];if(delta>0)t=ends.find(v=>v>t+1e-7)??data.duration;else t=ends.findLast(v=>v<t-1e-7)??0;lastFrame=-1;lastDecision=-2;}
  function tableRows(target,rows){$(target).replaceChildren(...rows.map(cells=>{const tr=document.createElement('tr');for(const text of cells){const td=document.createElement('td');td.textContent=text;tr.append(td);}return tr;}));}
  function updateLearning(){
    const i=completedDecision(),d=run.decisions[Math.max(0,i)],initial=i<0;
    $('previous-step').disabled=t<=0;$('next-step').disabled=t>=data.duration;
    $('step-position').textContent=`已完成 ${i+1} / ${run.decisions.length} 次决策 · 每步 ${data.simulation.delta_time} 秒`;
    if(!learning||i===lastDecision)return;lastDecision=i;
    $('decision-title').textContent=initial?'初始状态 · 尚未完成第一个决策':`第 ${d.index} 次决策 · ${clock(d.start)} → ${clock(d.end)}`;
    $('decision-timing').textContent=initial?'点击“下一步”，查看执行一个决策周期后的真实反馈。':`下方展示最近完成的决策，反馈截至 ${clock(d.end)}；主画面当前时刻为时间轴所示。`;
    $('state-summary').textContent=`决策前绿灯已持续 ${fmt(d.state.greenAge)} 秒。密度为车辆数与估计车道容量之比。`;
    tableRows('state-rows',[...'NSEW'].map(k=>[direction(k)+'进口',d.state.density[k]===null?'无进口':`${d.state.queue[k]} / ${initial?'—':d.nextState.queue[k]} 辆`,d.state.density[k]===null?'—':(d.state.density[k]*100).toFixed(1)+'%']));
    tableRows('vectors',run.observationLabels.map((label,j)=>[label,Number(d.observation[j]).toFixed(4),initial?'—':Number(d.nextObservation[j]).toFixed(4)]));
    $('requested-action').textContent=initial?'尚未展示':run.policy==='yield'?'持续开放全部入口':actionName(d.requested);
    $('executed-action').textContent=initial?'等待执行':run.policy==='yield'?'自然让行':actionName(d.executed);
    $('action-reason').textContent=initial?'完成一个决策步后显示实际控制结果。':reasons[d.reason];
    $('reward-total').textContent=initial?'—':fmt(d.reward);$('reward-scope').textContent=`停车项统计范围：${run.rewardScope}`;
    const weights={stopped:data.rewardWeights.queue_weight,imbalance:run.layout==='intersection'?data.rewardWeights.imbalance_weight:0,switch:data.rewardWeights.switch_weight,invalid:1};
    const labels={stopped:'停车车辆',imbalance:'南北/东西队列差',switch:'相位切换',invalid:'无效动作'};
    $('reward-terms').replaceChildren(...Object.entries(labels).map(([key,label])=>{const row=document.createElement('div');row.className='reward-line';const name=document.createElement('span'),v=document.createElement('b');name.textContent=initial?label:`${label} ${d.rewardInputs[key]} × 权重 ${weights[key]}`;v.textContent=initial?'—':fmt(d.rewardTerms[key]);row.append(name,v);return row;}));
    $('reward-formula').textContent=initial?'rₜ = 各奖励分项之和':Object.values(d.rewardTerms).map(v=>`(${fmt(v)})`).join(' + ')+` = ${fmt(d.reward)}`;
  }
  function updateUI(frame,index){
    $('time').textContent=clock(t);$('timeline').value=t;updateLearning();
    if(index===lastFrame)return;lastFrame=index;
    $('queue').textContent=frame.q.reduce((a,b)=>a+b,0);$('completed').textContent=frame.completed;$('avg-speed').textContent=frame.speed===null?'—':frame.speed.toFixed(1);
    frame.q.forEach((q,i)=>{$(`q-${i}`).textContent=frame.light[i]==='-'?'—':q;$(`bar-${i}`).style.width=`${Math.min(100,q/Math.max(10,...frame.q)*100)}%`;});
    [...frame.light].forEach((c,i)=>{const color=c.toLowerCase();$(`signal-${i}`).querySelectorAll('i').forEach(el=>el.classList.toggle('lit',el.dataset.color===color));$(`signal-${i}-label`).textContent=color==='g'?'通行':color==='y'?'过渡':color==='-'?'无进口':'等待';});
    $('phase-label').textContent=run.policy==='yield'?'入口开放 · 环内优先':frame.light.includes('y')?'黄灯过渡':frame.light.toLowerCase().includes('g')?[...frame.light].map((c,i)=>c.toLowerCase()==='g'?'北南东西'[i]:'').join('')+'放行':'全红清空';
    const d=run.decisions[completedDecision()];$('last-action').textContent=d?`最近完成决策 ${clock(d.end)}：${reasons[d.reason]}`:'尚未完成第一个决策。';
    const values=run.frames.slice(Math.max(0,index-150),index+1).filter((_,j)=>j%5===0).map(f=>f.speed||0);$('spark').setAttribute('d',values.map((v,j)=>`${j?'L':'M'}${j/Math.max(1,values.length-1)*140} ${33-Math.min(45,v)/45*30}`).join(' '));
  }
  options($('layout'),data.layouts.map(s=>s.id),layoutNames,run.layout);options($('policy'),[],policyNames,'');rebuildScenarios();chooseRun(true);
  for(const [i,label] of ['北进口','南进口','东进口','西进口'].entries()){const row=document.createElement('div');row.className='q-row';row.innerHTML=`<span>${label}</span><div class="bar"><div class="fill" id="bar-${i}"></div></div><b id="q-${i}">0</b>`;$('direction-queues').append(row);}
  document.querySelectorAll('.signal-row').forEach(el=>el.remove());for(const [i,label] of ['北','南','东','西'].entries()){const row=document.createElement('div');row.className='signal-row';row.innerHTML=`<span>${label}进口</span><div class="traffic-light" id="signal-${i}"><i data-color="r"></i><i data-color="y"></i><i data-color="g"></i></div><b id="signal-${i}-label"></b>`;document.querySelector('.signal-panel').append(row);}
  $('layout').onchange=()=>{rebuildScenarios();chooseRun(true);};$('policy').onchange=()=>chooseRun(false);
  $('demo-mode').onclick=()=>setMode(false);$('learn-mode').onclick=()=>setMode(true);
  $('play').onclick=()=>{if(t>=data.duration)t=0;setPlaying(!playing);};$('restart').onclick=()=>{t=0;lastFrame=-1;lastDecision=-2;setPlaying(false);};
  $('timeline').max=data.duration;$('duration').textContent=clock(data.duration);$('timeline').oninput=e=>{t=Number(e.target.value);setPlaying(false);lastFrame=-1;lastDecision=-2;};
  $('speed').onchange=e=>speed=Number(e.target.value);$('previous-step').onclick=()=>step(-1);$('next-step').onclick=()=>step(1);
  $('zoom-in').onclick=()=>renderer.setZoom(renderer.zoom*1.2);$('zoom-out').onclick=()=>renderer.setZoom(renderer.zoom/1.2);$('reset-view').onclick=()=>renderer.reset();
  const focusButton=$('fullscreen'),focusHome=focusButton.parentElement;focusButton.onclick=()=>{const active=document.body.classList.toggle('focus');(active?document.querySelector('.top'):focusHome).append(focusButton);focusButton.setAttribute('aria-pressed',active);focusButton.querySelector('span').textContent=active?'退出专注':'专注演示';};
  const openDialog=id=>{setPlaying(false);$(id).showModal();};$('guide-open').onclick=()=>openDialog('guide-dialog');$('info-open').onclick=()=>{updateInfo();openDialog('info-dialog');};
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());$('guide-learn').onclick=()=>{$('guide-dialog').close();setMode(true);};
  document.querySelectorAll('[data-concept]').forEach(b=>b.onclick=()=>{const [title,body]=concepts[b.dataset.concept];$('concept-title').textContent=title;$('concept-body').textContent=body;openDialog('concept-dialog');});
  document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]')||['INPUT','SELECT','BUTTON','SUMMARY'].includes(document.activeElement.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click();}if(learning&&['ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();step(e.key==='ArrowRight'?1:-1);}});
  document.addEventListener('visibilitychange',()=>{last=null;fpsStart=null;fpsFrames=0;});
  function animate(now){
    const elapsed=last===null?0:Math.min((now-last)/1000,.1);last=now;if(playing){t=Math.min(data.duration,t+elapsed*speed);if(t>=data.duration)setPlaying(false);}
    const frames=run.frames;let i=Math.min(frames.length-1,Math.floor(t/data.sampleInterval));while(i>0&&frames[i].t>t)i--;while(i+1<frames.length&&frames[i+1].t<=t)i++;
    const f=frames[i],next=frames[Math.min(i+1,frames.length-1)],a=next.t>f.t?(t-f.t)/(next.t-f.t):0;
    const d=run.decisions[completedDecision()];const highlight=learning&&d?(run.policy==='yield'?[...'NSEW']:run.layout==='intersection'?(d.executed===0?['N','S']:['E','W']):['NSEW'[d.executed]]):[];
    renderer.draw(f,next,a,highlight);updateUI(f,i);fpsFrames++;if(fpsStart===null)fpsStart=now;if(now-fpsStart>=1000){$('fps').textContent=` · ${Math.round(fpsFrames*1000/(now-fpsStart))} FPS`;fpsStart=now;fpsFrames=0;}
    requestAnimationFrame(animate);
  }
  setPlaying(false);requestAnimationFrame(animate);
})();
