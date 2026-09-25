/* Render SUMO geometry; static roads are cached separately from moving vehicles. */
window.TrafficRenderer = class {
  constructor(canvas) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d');
    this.background=document.createElement('canvas'); this.bg=this.background.getContext('2d');
    this.w=0;this.h=0;this.zoom=1;this.pan=[0,0];this.dirty=true;this.drag=null;
    new ResizeObserver(()=>this.resize()).observe(canvas);
    canvas.addEventListener('pointerdown',e=>{this.drag=[e.clientX,e.clientY,...this.pan];canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{if(this.drag){this.pan=[this.drag[2]+e.clientX-this.drag[0],this.drag[3]+e.clientY-this.drag[1]];this.dirty=true;}});
    for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{this.drag=null;});
    canvas.addEventListener('wheel',e=>{e.preventDefault();this.setZoom(this.zoom*(e.deltaY<0?1.1:1/1.1));},{passive:false});
  }
  resize(){const r=this.canvas.getBoundingClientRect();this.w=r.width;this.h=r.height;this.dpr=Math.min(devicePixelRatio||1,2);for(const c of [this.canvas,this.background]){c.width=Math.round(this.w*this.dpr);c.height=Math.round(this.h*this.dpr);}this.ctx.setTransform(this.dpr,0,0,this.dpr,0,0);this.bg.setTransform(this.dpr,0,0,this.dpr,0,0);this.dirty=true;}
  setScene(scene){this.scene=scene;this.reset();}
  reset(){this.zoom=1;this.pan=[0,0];this.dirty=true;}
  setZoom(value){this.zoom=Math.max(.35,Math.min(3,value));this.dirty=true;}
  point(x,y){return [this.w/2+(x-this.scene.center[0])*this.scale+this.pan[0],this.h/2-(y-this.scene.center[1])*this.scale+this.pan[1]];}
  path(ctx,shape,close=false){ctx.beginPath();shape.forEach(([x,y],i)=>{const p=this.point(x,y);if(i)ctx.lineTo(...p);else ctx.moveTo(...p);});if(close)ctx.closePath();}
  arrow(ctx,p,angle){const [x,y]=this.point(...p);ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.strokeStyle='#c8d6c0';ctx.lineWidth=Math.max(.7,this.scale*.25);ctx.beginPath();ctx.moveTo(-2*this.scale,0);ctx.lineTo(2*this.scale,0);ctx.moveTo(.6*this.scale,-.8*this.scale);ctx.lineTo(2*this.scale,0);ctx.lineTo(.6*this.scale,.8*this.scale);ctx.stroke();ctx.restore();}
  staticScene(){
    const ctx=this.bg,g=this.scene.geometry;ctx.clearRect(0,0,this.w,this.h);ctx.fillStyle='#e8efe2';ctx.fillRect(0,0,this.w,this.h);
    for(const x of [-68,68])for(const y of [-45,-28,28,45]){const p=this.point(this.scene.center[0]+x,this.scene.center[1]+y);ctx.fillStyle='#789d7425';ctx.beginPath();ctx.arc(p[0]+2,p[1]+3,2.5*this.scale,0,Math.PI*2);ctx.fill();ctx.fillStyle='#afc69e';ctx.beginPath();ctx.arc(...p,2.2*this.scale,0,Math.PI*2);ctx.fill();}
    for(const [extra,color] of [[2.2,'#becbbd'],[1.2,'#f7f5e9'],[0,'#344b50']]){
      ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineCap='round';ctx.lineJoin='round';
      for(const lane of g.lanes){this.path(ctx,lane.shape);ctx.lineWidth=(lane.width+extra)*this.scale;ctx.stroke();}
      for(const shape of g.junctions){this.path(ctx,shape,true);ctx.fill();}
    }
    // In/out directions are derived from actual lane point order.
    for(const lane of g.lanes.filter(l=>!l.id.startsWith(':'))){
      ctx.strokeStyle='#c9d6c339';ctx.lineWidth=Math.max(.5,.13*this.scale);ctx.setLineDash([2*this.scale,3*this.scale]);this.path(ctx,lane.shape);ctx.stroke();ctx.setLineDash([]);
      const shape=lane.shape;
      if(lane.id.startsWith('ring_')){const i=Math.floor(shape.length/2);const a=shape[i-1],b=shape[i];this.arrow(ctx,b,Math.atan2(-(b[1]-a[1]),b[0]-a[0]));}
      else if(/_(in|out)_0$/.test(lane.id)){const a=shape[0],b=shape.at(-1),length=Math.hypot(b[0]-a[0],b[1]-a[1]);const f=lane.id.includes('_in_')?Math.max(0,1-14/length):Math.min(1,14/length);this.arrow(ctx,[a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1])],Math.atan2(-(b[1]-a[1]),b[0]-a[0]));}
    }
    for(const signal of g.signals){const lane=g.lanes.find(l=>l.id===signal.direction+'_in_0');if(!lane)continue;const a=lane.shape.at(-2),b=lane.shape.at(-1),len=Math.hypot(b[0]-a[0],b[1]-a[1]);const normal=[-(b[1]-a[1])/len*1.5,(b[0]-a[0])/len*1.5];this.path(ctx,[[b[0]-normal[0],b[1]-normal[1]],[b[0]+normal[0],b[1]+normal[1]]]);ctx.strokeStyle='#f0eee1';ctx.lineWidth=.5*this.scale;ctx.stroke();}
    if(this.scene.id==='roundabout'){for(const [x,y] of [[-7,5],[8,6],[0,-7]]){const p=this.point(this.scene.center[0]+x,this.scene.center[1]+y);ctx.fillStyle='#b1c89e';ctx.beginPath();ctx.arc(...p,3.6*this.scale,0,Math.PI*2);ctx.fill();}}
    ctx.font='10px "Microsoft YaHei",sans-serif';ctx.fillStyle='#6d856b';ctx.textAlign='center';for(const [d,x,y] of [['北 N',12,56],['南 S',-12,-56],['东 E',76,12],['西 W',-76,-12]]){if(this.scene.id==='tjunction'&&d==='北 N')continue;ctx.fillText(d,...this.point(this.scene.center[0]+x,this.scene.center[1]+y));}
    this.dirty=false;
  }
  draw(frame,next,alpha,highlight=[]){
    if(!this.scene||!this.w)return;this.scale=Math.min(this.w/190,this.h/132)*this.zoom;if(this.dirty)this.staticScene();
    const ctx=this.ctx;ctx.clearRect(0,0,this.w,this.h);ctx.drawImage(this.background,0,0,this.w,this.h);
    for(const signal of this.scene.geometry.signals){if(highlight.includes(signal.direction)){const p=this.point(...signal.position);ctx.fillStyle='#e3b84844';ctx.beginPath();ctx.arc(...p,9*this.scale,0,Math.PI*2);ctx.fill();}}
    const following=new Map(next.v.map(v=>[v[0],v]));
    for(const v of frame.v){const n=following.get(v[0]),x=v[1]+(n?(n[1]-v[1])*alpha:0),y=v[2]+(n?(n[2]-v[2])*alpha:0);const p=this.point(x,y);if(p[0]<-25||p[0]>this.w+25||p[1]<-25||p[1]>this.h+25)continue;
      ctx.save();ctx.translate(...p);ctx.rotate((v[3]+(n?((n[3]-v[3]+540)%360-180)*alpha:0))*Math.PI/180);const width=1.8*this.scale,length=4.7*this.scale;
      ctx.fillStyle='#153c3430';ctx.fillRect(-width/2+1,1,width,length);ctx.fillStyle=v[4]<.5?'#dba158':['#248f78','#d7e4df','#76a5a9','#8abca9'][v[0]%4];ctx.beginPath();ctx.roundRect(-width/2,0,width,length,Math.max(.6,width*.2));ctx.fill();ctx.fillStyle='#315454';ctx.fillRect(-width*.35,length*.2,width*.7,length*.18);ctx.fillRect(-width*.33,length*.67,width*.66,length*.12);ctx.fillStyle='#f4edcb';ctx.fillRect(-width*.4,0,width*.25,Math.max(.6,.2*this.scale));ctx.fillRect(width*.15,0,width*.25,Math.max(.6,.2*this.scale));ctx.restore();
    }
    for(const s of this.scene.geometry.signals){const color=frame.light['NSEW'.indexOf(s.direction)]?.toLowerCase();if(color==='-')continue;const p=this.point(...s.position);ctx.fillStyle='#193d34';ctx.beginPath();ctx.roundRect(p[0]-5,p[1]-5,10,10,3);ctx.fill();ctx.fillStyle=color==='g'?'#70d5a4':color==='y'?'#f0bc58':'#e87f72';ctx.beginPath();ctx.arc(...p,2.8,0,Math.PI*2);ctx.fill();}
  }
};
