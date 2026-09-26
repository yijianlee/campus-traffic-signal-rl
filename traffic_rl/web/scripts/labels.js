window.TrafficLabels = (() => {
  const layoutNames={intersection:'直行十字路口',crossroads:'转弯十字路口',tjunction:'丁字路口',roundabout:'入口受控环岛'};
  const scenarioNames={balanced:'均衡车流',peak:'高峰车流',tidal:'潮汐车流',surge:'突发车流'};
  const policyNames={fixed:'固定配时',queue:'排队优先',yield:'自然让行',dqn:'DQN 策略'};
  const notes={fixed:'按预设时长轮流放行，遵守信号时长约束。',queue:'优先服务排队较多的方向，仍受最小、最大绿灯约束。',yield:'入口持续开放，驶入车辆向环内车辆让行。',dqn:'加载已有模型进行确定性评估，回放期间不更新参数。'};
  const reasons={hold:'保持当前放行方向。',switch:'执行方向切换，并经过信号过渡。',min_green:'最小绿灯尚未满足，请求切换被暂缓，保持原方向。',max_green:'最长绿灯保护触发，控制器强制切换方向。',invalid:'请求的进口不存在，保持原方向并计入无效动作惩罚。',unmetered:'入口全部开放，信号不限制进入；环岛合流处仍按环内优先让行。'};
  const concepts={state:['状态 sₜ','智能体在决策时看到的数值。这里包括排队、密度、放行相位等。中文表格帮助理解路况，展开向量可查看实际输入模型的归一化数值。'],action:['动作 aₜ','策略希望放行的方向。旧路口有南北/东西两种动作，新道路有北/南/东/西四种。控制器还会检查最小绿灯、最长绿灯和进口是否存在，因此请求不一定原样执行。'],reward:['奖励 rₜ','执行动作后，环境计算的反馈分数。本例以停车车辆数的负值为主，加上配置的惩罚项。DQN 训练旨在提高累积折扣回报，而不是只追求某一步的最高分。'],episode:['回合 Episode','一次从仿真开始到设定时长结束的完整运行，包含多次决策。训练会经历多个回合并更新参数；此页面只回放已记录的评估回合。']};
  return {layoutNames,scenarioNames,policyNames,notes,reasons,concepts};
})();
