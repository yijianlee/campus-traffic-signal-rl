(() => {
  'use strict';
  const data = window.TRAFFIC_REPLAY;
  const $ = id => document.getElementById(id);
  if (!data?.runs?.length) { $('error').hidden = false; $('error').textContent = '未找到仿真记录。请重新运行 show 命令，并将页面与 recordings.js 保存在同一目录。'; return; }
  const titles = {fixed:'固定配时', queue:'排队优先', dqn:'DQN 智能策略'};
  const scenarios = {balanced:'均衡车流', peak:'高峰车流', tidal:'潮汐车流'};
  const notes = {fixed:'按预设时长轮流放行。观察稳定节奏如何应对不同方向的车流。', queue:'优先服务排队较多的方向，同时遵守最短、最长绿灯限制。', dqn:'根据路口状态选择动作。' + (data.modelNote || '策略效果需通过独立实验评估。')};
  const policies = [...new Set(data.runs.map(r => r.policy))];
  $('policy').replaceChildren(...policies.map(p => { const o = document.createElement('option'); o.value = p; o.textContent = titles[p]; return o; }));
  document.querySelectorAll('[data-scenario]').forEach(b => { b.disabled = !data.runs.some(r => r.scenario === b.dataset.scenario); });
  $('seed').textContent = `同一到达记录 · SEED ${data.seed}`;
  const canvas = $('map'), ctx = canvas.getContext('2d');
  let run = data.runs[0], t = 0, playing = false, speed = 3, radius = 95, last = null;
  let w = 0, h = 0, scale = 1, frameIndex = 0, lastUI = -1;
  const clock = value => `${Math.floor(value/60).toString().padStart(2,'0')}:${Math.floor(value%60).toString().padStart(2,'0')}`;
  $('timeline').max = data.duration; $('duration').textContent = clock(data.duration);
  for (const [i, label] of ['北进口','南进口','东进口','西进口'].entries()) {
    const row = document.createElement('div'); row.className = 'q-row';
    row.innerHTML = `<span>${label}</span><div class="bar"><div class="fill" id="bar-${i}"></div></div><b id="q-${i}">0</b>`;
    $('direction-queues').append(row);
  }
  function refreshRun() {
    const scene = document.querySelector('[data-scenario].active')?.dataset.scenario || run.scenario;
    run = data.runs.find(r => r.scenario === scene && r.policy === $('policy').value) || data.runs[0];
    document.querySelectorAll('[data-scenario]').forEach(b => b.classList.toggle('active', b.dataset.scenario === run.scenario));
    $('policy').value = run.policy;
    $('policy-title').textContent = titles[run.policy]; $('policy-note').textContent = notes[run.policy];
    $('run-description').textContent = `${scenarios[run.scenario]} / ${titles[run.policy]} · ${run.planned} 辆计划到达 · ${data.duration} 秒记录。策略切换保留当前回放时刻。`;
    $('final-wait').innerHTML = `${run.metrics.mean_wait_plus_entry_delay_all_s.toFixed(1)}<small>秒</small>`;
    $('completion-rate').textContent = `${(100*run.metrics.completion_rate).toFixed(1)}%`;
    lastUI = -1;
  }
  function setPlaying(value) {
    playing = value;
    $('play').textContent = playing ? 'Ⅱ 暂停回放' : '▶ 播放回放';
    $('state-label').textContent = playing ? '正在回放' : t >= data.duration ? '回放结束' : '已暂停';
  }
  document.querySelectorAll('[data-scenario]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-scenario]').forEach(other => other.classList.remove('active'));
    b.classList.add('active'); refreshRun();
  }));
  $('policy').addEventListener('change', refreshRun);
  $('play').onclick = () => { if (t >= data.duration) t = 0; setPlaying(!playing); };
  $('restart').onclick = () => { t = 0; lastUI = -1; setPlaying(false); };
  $('speed').onchange = e => { speed = Number(e.target.value); };
  $('timeline').oninput = e => { t = Number(e.target.value); lastUI = -1; if (t >= data.duration) setPlaying(false); };
  $('zoom-in').onclick = () => { radius = Math.max(55, radius - 15); };
  $('zoom-out').onclick = () => { radius = Math.min(260, radius + 15); };
  const focusButton = $('fullscreen'), focusHome = focusButton.parentElement;
  focusButton.onclick = () => {
    const active = document.body.classList.toggle('focus');
    (active ? document.querySelector('.top') : focusHome).append(focusButton);
    focusButton.setAttribute('aria-pressed', active);
    focusButton.querySelector('span').textContent = active ? '退出专注' : '专注演示';
    focusButton.setAttribute('aria-label', active ? '退出专注演示' : '专注演示');
  };
  document.addEventListener('keydown', e => { if (e.code === 'Space' && !['INPUT','SELECT','BUTTON'].includes(document.activeElement.tagName)) { e.preventDefault(); $('play').click(); } });
  document.addEventListener('visibilitychange', () => { last = null; });
  new ResizeObserver(() => {
    const rect = canvas.getBoundingClientRect(); w = rect.width; h = rect.height;
    const dpr = Math.min(devicePixelRatio || 1, 2); canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr); ctx.setTransform(dpr,0,0,dpr,0,0);
  }).observe(canvas);
  const X = x => w/2 + x*scale, Y = y => h/2 - y*scale;
  function rounded(x,y,width,height,r,color) { ctx.fillStyle=color; ctx.beginPath(); ctx.roundRect(x,y,width,height,r); ctx.fill(); }
  function line(x1,y1,x2,y2,color,width=1,dash=[]) { ctx.beginPath(); ctx.setLineDash(dash); ctx.strokeStyle=color; ctx.lineWidth=width; ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]); }
  function text(label,x,y,size=10,color='#6f8876',align='center') {ctx.font=`${size}px "Segoe UI","Microsoft YaHei",sans-serif`;ctx.textAlign=align;ctx.fillStyle=color;ctx.fillText(label,x,y);}
  function tree(x,y,r=2.1) { x=X(x);y=Y(y);r*=scale;ctx.fillStyle='#1b583619';ctx.beginPath();ctx.ellipse(x+2,y+3,r,r*.8,0,0,7);ctx.fill();ctx.fillStyle='#a5bfa0';ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fill();ctx.fillStyle='#bcd0ad';ctx.beginPath();ctx.arc(x-r*.22,y-r*.22,r*.63,0,7);ctx.fill(); }
  function building(x,y,bw,bh,label,color='#d8dfd0') {const bx=X(x),by=Y(y);rounded(bx+4,by+6,bw*scale,bh*scale,3,'#36563813');rounded(bx,by,bw*scale,bh*scale,3,'#c0cbbc');rounded(bx+2,by+2,bw*scale-4,bh*scale-5,2,color);ctx.strokeStyle='#edf0e6';ctx.lineWidth=1;ctx.strokeRect(bx+5,by+5,bw*scale-10,bh*scale-12);for(let i=0;i<3;i++)rounded(bx+9+i*7,by+8,4,8,1,'#abbfac');text(label,bx+bw*scale/2,by+bh*scale/2+9,10,'#778673'); }
  function scene() {
    ctx.clearRect(0,0,w,h); ctx.fillStyle='#e8efe4';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#dfe8d9';ctx.lineWidth=.7;for(let x=0;x<w;x+=36){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}for(let y=0;y<h;y+=36){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
    rounded(X(-87),Y(49),64*scale,34*scale,10,'#dce8d1');rounded(X(23),Y(-17),63*scale,34*scale,10,'#dce8d1');
    building(-69,39,31,17,'教学楼');building(32,41,32,18,'图书馆','#d5ddcc');building(-73,-25,35,17,'创新中心');
    // Decorative campus park: no pedestrians or additional traffic simulated.
    ctx.strokeStyle='#f4f6e8';ctx.lineWidth=3*scale;ctx.beginPath();ctx.ellipse(X(53),Y(-34),19*scale,9*scale,-.2,0,Math.PI*2);ctx.stroke();text('CAMPUS GARDEN',X(53),Y(-34)+3,8,'#90a17f');
    for(const x of [-22,22])for(const y of [-49,-36,-23,23,36,49])tree(x,y,1.8);
    for(const y of [-18,18])for(const x of [-83,-68,-53,-38,38,53,68,83])tree(x,y,1.7);
    tree(-80,42,3);tree(79,34,3);tree(74,-40,2.8);tree(-28,-45,2.8);
    // All vehicle locations use the unmodified SUMO world coordinates.
    ctx.fillStyle='#c6d1c6';ctx.fillRect(X(-8.4),0,16.8*scale,h);ctx.fillRect(0,Y(8.4),w,16.8*scale);
    ctx.fillStyle='#f3f2e8';ctx.fillRect(X(-7.5),0,15*scale,h);ctx.fillRect(0,Y(7.5),w,15*scale);
    ctx.fillStyle='#344b50';ctx.fillRect(X(-5.4),0,10.8*scale,h);ctx.fillRect(0,Y(5.4),w,10.8*scale);
    ctx.fillStyle='#30464c';ctx.fillRect(X(-7.2),Y(7.2),14.4*scale,14.4*scale);
    const dash=[3*scale,3*scale];for(const sign of [-1,1]){
      line(X(sign*.22),0,X(sign*.22),Y(10),'#d3bf88',.25*scale,dash);line(X(sign*.22),Y(-10),X(sign*.22),h,'#d3bf88',.25*scale,dash);
      line(0,Y(sign*.22),X(-10),Y(sign*.22),'#d3bf88',.25*scale,dash);line(X(10),Y(sign*.22),w,Y(sign*.22),'#d3bf88',.25*scale,dash);
      line(X(sign*3.7),0,X(sign*3.7),Y(8),'#9bb0ad',.12*scale);line(X(sign*3.7),Y(-8),X(sign*3.7),h,'#9bb0ad',.12*scale);
      line(0,Y(sign*3.7),X(-8),Y(sign*3.7),'#9bb0ad',.12*scale);line(X(8),Y(sign*3.7),w,Y(sign*3.7),'#9bb0ad',.12*scale);
    }
    line(X(-3.2),Y(8.3),X(0),Y(8.3),'#eff1e5',.55*scale);line(X(0),Y(-8.3),X(3.2),Y(-8.3),'#eff1e5',.55*scale);
    line(X(8.3),Y(0),X(8.3),Y(3.2),'#eff1e5',.55*scale);line(X(-8.3),Y(-3.2),X(-8.3),Y(0),'#eff1e5',.55*scale);
    // Lane arrows point in the same directions as the actual incoming lanes.
    for(const [x,y,angle] of [[-1.6,24,180],[1.6,-24,0],[24,1.6,270],[-24,-1.6,90]]) {ctx.save();ctx.translate(X(x),Y(y));ctx.rotate(angle*Math.PI/180);ctx.strokeStyle='#c8d2c8';ctx.lineWidth=.27*scale;ctx.beginPath();ctx.moveTo(0,2*scale);ctx.lineTo(0,-2*scale);ctx.moveTo(-.8*scale,-1.2*scale);ctx.lineTo(0,-2*scale);ctx.lineTo(.8*scale,-1.2*scale);ctx.stroke();ctx.restore();}
    text('北 · N',X(11),Y(42),10);text('南 · S',X(-12),Y(-44),10);text('西 · W',X(-67),Y(-11),10);text('东 · E',X(68),Y(11),10);
  }
  function lamp(x,y,color) {const fill=color.toLowerCase()==='g'?'#66d5a7':color==='y'?'#f2bf5a':'#ee8278';ctx.save();ctx.translate(X(x),Y(y));rounded(-6,-6,12,12,4,'#203c37');ctx.shadowBlur=9;ctx.shadowColor=fill;ctx.fillStyle=fill;ctx.beginPath();ctx.arc(0,0,3.1,0,7);ctx.fill();ctx.restore();}
  function car(v,next,a) {
    const x = v[1] + (next ? (next[1]-v[1])*a : 0) - data.center[0];
    const y = v[2] + (next ? (next[2]-v[2])*a : 0) - data.center[1];
    if(X(x)<-30||X(x)>w+30||Y(y)<-30||Y(y)>h+30)return;
    ctx.save();ctx.translate(X(x),Y(y));ctx.rotate(v[3]*Math.PI/180);
    // SUMO positions are vehicle front bumpers; draw the body behind them.
    const cw=1.8*scale,cl=4.7*scale;
    rounded(-cw/2+1,1,cw,cl,Math.max(1,cw*.22),'#102d3533');
    const colors=['#258d78','#d5e2df','#6f9da4','#87bbae'];const color=v[4]<.5?'#dca55c':colors[v[0]%colors.length];
    rounded(-cw/2,0,cw,cl,Math.max(1,cw*.22),color);
    rounded(-cw*.36,cl*.2,cw*.72,cl*.19,1,'#25494e');rounded(-cw*.34,cl*.67,cw*.68,cl*.13,1,'#365c5a');
    ctx.fillStyle='#f4edcf';ctx.fillRect(-cw*.38,1,cw*.22,Math.max(1,scale*.2));ctx.fillRect(cw*.16,1,cw*.22,Math.max(1,scale*.2));
    if(v[4]<.5){ctx.fillStyle='#ea7461';ctx.fillRect(-cw*.4,cl-2,cw*.2,2);ctx.fillRect(cw*.2,cl-2,cw*.2,2);}ctx.restore();
  }
  function ui(frame,index) {
    $('time').textContent=clock(t);$('timeline').value=t;
    if(index===lastUI)return;lastUI=index;
    $('queue').textContent=frame.q.reduce((a,b)=>a+b,0);$('completed').textContent=frame.completed;
    $('avg-speed').textContent=frame.speed===null?'—':frame.speed.toFixed(1);
    frame.q.forEach((v,i)=>{$(`q-${i}`).textContent=v;$(`bar-${i}`).style.width=`${Math.min(100,v/Math.max(10,...frame.q)*100)}%`;});
    for(const [id,color] of [['ns',frame.light[0]],['ew',frame.light[2]]]){const c=color.toLowerCase();$(id).querySelectorAll('i').forEach(el=>el.classList.toggle('lit',el.dataset.color===c));$(`${id}-label`).textContent=c==='g'?'通行':c==='y'?'过渡':'等待';}
    $('phase-label').textContent=frame.light.includes('y')?'黄灯过渡':frame.light[0].toLowerCase()==='g'?'南北放行':'东西放行';
    const values=run.frames.slice(Math.max(0,index-150),index+1).filter((_,i)=>i%5===0).map(f=>f.speed||0);
    $('spark').setAttribute('d',values.map((v,i)=>`${i?'L':'M'}${i/Math.max(1,values.length-1)*140} ${33-Math.min(45,v)/45*30}`).join(' '));
  }
  function animate(now) {
    const elapsed=last===null?0:Math.min((now-last)/1000,.1);last=now;
    if(playing){t=Math.min(data.duration,t+elapsed*speed);if(t>=data.duration)setPlaying(false);}
    scale=Math.min(w/190,h/125)*95/radius;
    const frames=run.frames;frameIndex=Math.min(frames.length-1,Math.floor(t/data.sampleInterval));
    // FCD samples are evenly spaced, but locate defensively at the boundary.
    while(frameIndex>0&&frames[frameIndex].t>t)frameIndex--;
    while(frameIndex+1<frames.length&&frames[frameIndex+1].t<=t)frameIndex++;
    const f=frames[frameIndex],next=frames[Math.min(frameIndex+1,frames.length-1)];
    const alpha=next.t>f.t?Math.max(0,Math.min(1,(t-f.t)/(next.t-f.t))):0;
    scene();const nextById=new Map(next.v.map(v=>[v[0],v]));for(const v of f.v)car(v,nextById.get(v[0]),alpha);
    lamp(-7,10,f.light[0]);lamp(7,-10,f.light[1]);lamp(10,7,f.light[2]);lamp(-10,-7,f.light[3]);
    ui(f,frameIndex);requestAnimationFrame(animate);
  }
  refreshRun();setPlaying(false);requestAnimationFrame(animate);
})();
