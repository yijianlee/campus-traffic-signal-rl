(async () => {
  'use strict';
  const data=window.TRAFFIC_REPLAY, $=id=>document.getElementById(id);
  if(!data?.runs?.length||!data.layouts?.length){$('error').hidden=false;$('error').textContent='这份记录缺少学习数据。请使用新版 show 命令重新导出，保留完整文件夹。';return;}
  const {layoutNames,scenarioNames,policyNames,notes,reasons,concepts}=window.TrafficLabels;
  let run=data.runs[0],scene=data.layouts.find(s=>s.id===run.layout),t=0,playing=false,learning=false,speed=1,last=null,lastFrame=-1,lastDecision=-2;
  let noticeTimer=null, loadVersion=0, loading=true;
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
  async function chooseRun(reset){
    const version=++loadVersion; loading=true; setPlaying(false); $("state-label").textContent="正在加载…"; $("error").hidden=true;
    const previous=$('policy').value, candidates=data.runs.filter(r=>r.layout===$('layout').value&&r.scenario===scenario);
    options($('policy'),candidates.map(r=>r.policy),policyNames,previous);
    const entry=candidates.find(r=>r.policy===$('policy').value);
    try {
      const loaded=await window.ReplayLoader.load(entry);
      if(version!==loadVersion)return;
      run=loaded; loading=false;
    } catch(error) {
      if(version!==loadVersion)return;
      $('error').hidden=false;$('error').textContent=error.message+'；重新选择策略可重试。';
      $('state-label').textContent='加载失败';return;
    }
    if(previous&&previous!==run.policy)notify('当前组合没有该策略记录，已切换为'+policyNames[run.policy]+'。');
    const nextScene=data.layouts.find(s=>s.id===run.layout);if(scene!==nextScene||!renderer.scene)renderer.setScene(nextScene);scene=nextScene;
    if(reset)t=0;
    setPlaying(false);
    $('map-title').textContent=layoutNames[run.layout];$('map-subtitle').textContent=run.layout==='roundabout'?' / 单车道 · 逆时针':' / SUMO 实际路网';

    $('policy-title').textContent=policyNames[run.policy];$('policy-note').textContent=notes[run.policy]+(run.policy==='dqn'?' '+(run.modelNote||data.modelNote||'训练程度未知。'):'');
    $('run-description').textContent=`${layoutNames[run.layout]} · ${scenarioNames[run.scenario]} · ${policyNames[run.policy]} · ${run.planned} 辆计划到达`;
    $('final-wait').replaceChildren(document.createTextNode(run.metrics.mean_wait_plus_entry_delay_all_s.toFixed(1)));const unit=document.createElement('small');unit.textContent='秒';$('final-wait').append(unit);
    $('completion-rate').textContent=(run.metrics.completion_rate*100).toFixed(1)+'%';
    lastFrame=-1;lastDecision=-2;updateInfo();
  }
  function updateInfo(){
    const items=[['道路',layoutNames[run.layout]],['车流',scenarioNames[run.scenario]],['策略',policyNames[run.policy]],['模型',run.policy==='dqn'?(run.modelNote||data.modelNote||'训练程度未知'):'规则基线，无模型参数更新'],['随机种子',data.seed],['回合长度',data.duration+' 秒'],['决策周期',data.simulation.delta_time+' 秒'],['物理步长',data.simulation.step_length+' 秒'],['绿灯范围',`${data.simulation.min_green}–${data.simulation.max_green} 秒`],['黄灯',data.simulation.yellow_time+' 秒'],['全红',run.layout==='intersection'?'旧布局无全红':(data.simulation.delta_time-data.simulation.yellow_time)+' 秒'],['奖励范围',run.rewardScope],['到达文件 SHA256',run.demandHash],['状态维度',run.observationLabels.length],['数据来源','合成车流，未实地校准']];
    window.paginate($('experiment-info'),items,5,(target,rows)=>{
      const list=document.createElement('dl');
      for(const [label,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;list.append(dt,dd);}
      target.replaceChildren(list);
    });
  }
  function setMode(value){learning=value;document.body.classList.toggle("learning-mode",value);setPlaying(false);$('learning').hidden=!value;$('step-controls').hidden=!value;$('demo-mode').classList.toggle('active',!value);$('learn-mode').classList.toggle('active',value);$('demo-mode').setAttribute('aria-pressed',!value);$('learn-mode').setAttribute('aria-pressed',value);$('demo').hidden=value;lastDecision=-2;}
  // At a boundary show the just-completed transition; never present future rewards as observed.
  function completedDecision(){let low=0,high=run.decisions.length;while(low<high){const m=(low+high)>>1;if(run.decisions[m].end<=t+1e-7)low=m+1;else high=m;}return low-1;}
  function step(delta){if(loading)return;setPlaying(false);const ends=[0,...run.decisions.map(d=>d.end)];if(delta>0)t=ends.find(v=>v>t+1e-7)??data.duration;else t=ends.findLast(v=>v<t-1e-7)??0;lastFrame=-1;lastDecision=-2;}
  function updateLearning(){
    const i=completedDecision();
    $('previous-step').disabled=t<=0;$('next-step').disabled=t>=data.duration;
    $('step-position').textContent=`已完成 ${i+1} / ${run.decisions.length} 次决策 · 每步 ${data.simulation.delta_time} 秒`;
    if(i===lastDecision)return;lastDecision=i;if(!learning)return;
    window.LearningPanel.render({run,data,i,clock,fmt,actionName,reasons});
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
  options($('layout'),data.layouts.map(s=>s.id),layoutNames,run.layout);options($('policy'),[],policyNames,'');rebuildScenarios();await chooseRun(true);
  for(const [i,label] of ['北进口','南进口','东进口','西进口'].entries()){const row=document.createElement('div');row.className='q-row';row.innerHTML=`<span>${label}</span><div class="bar"><div class="fill" id="bar-${i}"></div></div><b id="q-${i}">0</b>`;$('direction-queues').append(row);}
  document.querySelectorAll('.signal-row').forEach(el=>el.remove());for(const [i,label] of ['北','南','东','西'].entries()){const row=document.createElement('div');row.className='signal-row';row.innerHTML=`<span>${label}进口</span><div class="traffic-light" id="signal-${i}"><i data-color="r"></i><i data-color="y"></i><i data-color="g"></i></div><b id="signal-${i}-label"></b>`;document.querySelector('.signal-panel').append(row);}
  for(let i=0;i<4;i++) {
    const row=$(`signal-${i}`).parentElement;
    row.append($(`bar-${i}`).parentElement,$(`q-${i}`));
  }
  $('layout').onchange=()=>{rebuildScenarios();chooseRun(true);};$('policy').onchange=()=>chooseRun(false);
  $('demo-mode').onclick=()=>setMode(false);$('learn-mode').onclick=()=>setMode(true);
  $('play').onclick=()=>{if(loading)return;if(t>=data.duration)t=0;setPlaying(!playing);};$('restart').onclick=()=>{t=0;lastFrame=-1;lastDecision=-2;setPlaying(false);};
  $('timeline').max=data.duration;$('duration').textContent=clock(data.duration);$('timeline').oninput=e=>{t=Number(e.target.value);setPlaying(false);lastFrame=-1;lastDecision=-2;};
  $('speed').onchange=e=>speed=Number(e.target.value);$('previous-step').onclick=()=>step(-1);$('next-step').onclick=()=>step(1);
  $('zoom-in').onclick=()=>renderer.setZoom(renderer.zoom*1.2);$('zoom-out').onclick=()=>renderer.setZoom(renderer.zoom/1.2);$('reset-view').onclick=()=>renderer.reset();
  const openDialog=id=>{setPlaying(false);$(id).showModal();};$('guide-open').onclick=()=>openDialog('guide-dialog');$('info-open').onclick=()=>{updateInfo();openDialog('info-dialog');};
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());$('guide-learn').onclick=()=>{$('guide-dialog').close();setMode(true);};
  document.querySelectorAll('[data-concept]').forEach(b=>b.onclick=()=>{const [title,body]=concepts[b.dataset.concept];$('concept-title').textContent=title;$('concept-body').textContent=body;openDialog('concept-dialog');});

  $('current-tab').onclick=()=>{ $('current').hidden=false;$('results').hidden=true;$('current-tab').classList.add('active');$('results-tab').classList.remove('active'); };
  $('results-tab').onclick=()=>{ $('current').hidden=true;$('results').hidden=false;$('current-tab').classList.remove('active');$('results-tab').classList.add('active'); };
  const cards=[...document.querySelectorAll('.learning-card')];cards[0].classList.add('selected');
  document.querySelectorAll('[data-learning]').forEach(button=>button.onclick=()=>{
    document.querySelectorAll('[data-learning]').forEach(b=>b.classList.toggle('active',b===button));
    cards.forEach((card,i)=>card.classList.toggle('selected',i===Number(button.dataset.learning)));
  });
  $('vector-open').onclick=()=>{
    const i=completedDecision(),d=run.decisions[Math.max(0,i)];
    const rows=run.observationLabels.map((label,j)=>[label,Number(d.observation[j]).toFixed(4),i<0?'—':Number(d.nextObservation[j]).toFixed(4)]);
    window.paginate($('vectors'),rows,6,(target,subset)=>{
      const table=document.createElement('table');
      for(const cells of subset){const tr=document.createElement('tr');for(const text of cells){const td=document.createElement('td');td.textContent=text;tr.append(td);}table.append(tr);}
      target.replaceChildren(table);
    });openDialog('vector-dialog');
  };
  window.paginate($('guide-pages'),[
    ['观察路况','选择道路、车流和策略，再播放或拖动时间轴。同一组合的策略使用相同到达车流，便于比较。右侧可切换当前路况和整段结果。'],
    ['理解一次决策','进入学习模式，用下一步查看状态 → 请求动作 → 实际执行 → 奖励。初始时刻不展示尚未发生的反馈；方向切换受到绿灯时长约束。'],
    ['复现实验','本页回放已完成的 SUMO 评估，模型不会更新。车流为合成数据；分享时保留整个导出文件夹。训练、评估和团队分工见项目 docs 文档。']
  ],1,(target,rows)=>{const title=document.createElement('h3'),body=document.createElement('p');title.textContent=rows[0][0];body.textContent=rows[0][1];target.replaceChildren(title,body);});
  document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]')||['INPUT','SELECT','BUTTON','SUMMARY'].includes(document.activeElement.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click();}if(learning&&['ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();step(e.key==='ArrowRight'?1:-1);}});
  document.addEventListener('visibilitychange',()=>{last=null;});
  let lastDraw=0;
  function animate(now){
    requestAnimationFrame(animate);
    if(loading||now-lastDraw<1000/60)return;lastDraw=now;
    if(!playing&&!renderer.dirty&&lastFrame>=0&&lastDecision!==-2)return;
    const elapsed=last===null?0:Math.min((now-last)/1000,.1);last=now;if(playing){t=Math.min(data.duration,t+elapsed*speed);if(t>=data.duration)setPlaying(false);}
    const frames=run.frames;let i=Math.min(frames.length-1,Math.floor(t/data.sampleInterval));while(i>0&&frames[i].t>t)i--;while(i+1<frames.length&&frames[i+1].t<=t)i++;
    const f=frames[i],next=frames[Math.min(i+1,frames.length-1)],a=next.t>f.t?(t-f.t)/(next.t-f.t):0;
    const d=run.decisions[completedDecision()];const highlight=learning&&d?(run.policy==='yield'?[...'NSEW']:run.layout==='intersection'?(d.executed===0?['N','S']:['E','W']):['NSEW'[d.executed]]):[];
    renderer.draw(f,next,a,highlight);updateUI(f,i);
  }
  setPlaying(false);requestAnimationFrame(animate);
})();
