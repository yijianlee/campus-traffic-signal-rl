/* Display a completed transition; initial state never leaks a future reward. */
window.LearningPanel = (() => {
  const $=id=>document.getElementById(id);
  const direction=d=>({N:'北',S:'南',E:'东',W:'西'}[d]);
  function tableRows(target,rows){$(target).replaceChildren(...rows.map(cells=>{const tr=document.createElement('tr');for(const text of cells){const td=document.createElement('td');td.textContent=text;tr.append(td);}return tr;}));}
  function render({run,data,i,clock,fmt,actionName,reasons}) {
    const d=run.decisions[Math.max(0,i)],initial=i<0;
    $('decision-title').textContent=initial?'初始状态 · 尚未完成第一个决策':`第 ${d.index} 次决策 · ${clock(d.start)} → ${clock(d.end)}`;


    tableRows('state-rows',[...'NSEW'].map(k=>[direction(k)+'进口',d.state.density[k]===null?'无进口':`${d.state.queue[k]} / ${initial?'—':d.nextState.queue[k]} 辆`,d.state.density[k]===null?'—':(d.state.density[k]*100).toFixed(1)+'%']));

    $('requested-action').textContent=initial?'尚未展示':actionName(d.requested);
    $('executed-action').textContent=initial?'等待执行':actionName(d.executed);
    $('action-reason').textContent=initial?'完成一个决策步后显示实际控制结果。':reasons[d.reason];
    $('reward-total').textContent=initial?'—':fmt(d.reward);$('reward-scope').textContent=`停车项统计范围：${run.rewardScope}`;
    const weights={stopped:data.rewardWeights.queue_weight,switch:data.rewardWeights.switch_weight};
    const labels={stopped:'周期平均停车车辆',switch:'相位切换'};
    $('reward-terms').replaceChildren(...Object.entries(labels).map(([key,label])=>{const row=document.createElement('div');row.className='reward-line';const name=document.createElement('span'),v=document.createElement('b');name.textContent=initial?label:`${label} ${fmt(d.rewardInputs[key])} × 权重 ${weights[key]}`;v.textContent=initial?'—':fmt(d.rewardTerms[key]);row.append(name,v);return row;}));
    $('reward-formula').textContent=initial?'rₜ = 各奖励分项之和':Object.values(d.rewardTerms).map(v=>`(${fmt(v)})`).join(' + ')+` = ${fmt(d.reward)}`;
  }
  return {render};
})();
