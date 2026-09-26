# Traffic Signal RL

机器学习课程设计：**基于深度强化学习的十字路口信号控制优化**。

研究一个含直行、左转、右转的十字路口，在综合变化车流下训练 DQN，检验它能否比固定配时减少等待。前端仅展示 DQN 的评估记录。

## 运行

在项目根目录的 PowerShell 中执行；首次安装见 [快速开始](docs/quickstart.md)。

```powershell
.\.venv\Scripts\python.exe -m traffic_rl train --steps 30000 --out outputs/my_model
.\.venv\Scripts\python.exe -m traffic_rl evaluate --model outputs/my_model/model.zip --out outputs/my_evaluation
.\.venv\Scripts\python.exe -m traffic_rl show --model outputs/my_model/model.zip --out outputs/my_demo
```

输出目录必须使用新名字。训练生成模型和学习曲线；评估生成固定配时与 DQN 的结果表、对比图及报告；展示命令生成可回放网页。

## 代码

```text
traffic_rl/
  config.py       配置校验与 SUMO 路径
  network.py      唯一十字路口
  demand.py       综合车流生成
  env.py          状态、动作、奖励和信号约束
  agent.py        DQN 创建与加载
  train.py        训练、保存和学习曲线
  evaluate.py     固定配时对照、独立测试
  metrics.py      等待、队列与完成率
  replay.py       真实轨迹与决策导出
  package.py      网页资源与轨迹打包
  artifacts.py    输出目录与运行版本记录
  doctor.py       环境检查
  __main__.py     命令入口
  web/            单屏展示
configs/          参数
tests/           关键正确性测试
docs/            学习与报告说明
```

## 学习入口

- [快速开始](docs/quickstart.md)：安装与运行。
- [模型与代码](docs/learning.md)：14 维状态、4 个动作和奖励。
- [实验设计](docs/experiments.md)：复现、指标与改进实验。
- [课程报告框架](docs/report.md)：从问题到结论的写作顺序。

数据为合成交通，未经实地校准。DQN 不保证优于固定配时。旧版多路网命令已移除，旧 13/22 维模型需重新训练；历史版本保留在 Git 中。`outputs/` 和生成路网不入库。
