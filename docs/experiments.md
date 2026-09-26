# 训练与评估

训练覆盖三种新道路和四种车流：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl train --layout mixed --scenario mixed --steps 30000 --out outputs/diverse_dqn
```

评估时按道路分别运行，统一车流、时长和种子：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl evaluate --layout roundabout --policies fixed queue yield dqn --model outputs/diverse_dqn/model.zip --scenarios balanced peak tidal surge --seeds 101 102 103
.\.venv\Scripts\python.exe -m traffic_rl show --layouts crossroads tjunction roundabout --scenarios balanced peak surge --model outputs/diverse_dqn/model.zip --seconds 300
```

`yield` 仅用于环岛。旧路口 `intersection` 不支持 `surge`，多路网导出时自动跳过该组合。旧模型仅兼容旧路口；不指定 `--layout` 的旧命令行为保持不变。

| 产物 | 用途 |
|---|---|
| model.zip、run.json | 模型、训练步数、参数和复现信息 |
| summary.csv、report.md | 各策略评估结果 |
| tripinfo.xml、trace.csv | 行程数据、逐步状态与奖励 |
| index.html、manifest.json | 离线实验台与运行配置 |

重点比较平均等待加入网延迟、完成率、未完成车辆数、停车队列和安全事件。未完成车辆不能从等待统计中简单丢弃；具体口径见 `experiments/metrics.py`。

使用多个训练种子、独立评估种子，报告均值与波动。短程训练只用于验证流程，不能说明 DQN 已收敛或优于规则策略。数据为合成交通，现实结论需要实地校准。

默认配置见 `configs/default.json`；一次只改变一个因素。训练必须超过 `learning_starts`，程序会验证参数实际改变、保存和重新加载成功。

运行回归测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

测试覆盖路网与需求复现、控制约束、环境空间、奖励拆解、指标、离线分包，以及重构前后逐步行为一致性。历史研究计划与资源保留在 [archive](archive/experiment_plan.md)。
