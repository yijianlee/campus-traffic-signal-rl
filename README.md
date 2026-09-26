# Campus Traffic Signal RL

面向强化学习入门与课程团队展示的交通信号控制项目，基于 SUMO、Gymnasium 和 DQN。

支持直行/转弯十字路口、丁字路口、入口受控环岛；通过固定配时、排队优先和自然让行基线评估策略效果。

## 开始使用

```powershell
.\.venv\Scripts\python.exe -m traffic_rl doctor
.\.venv\Scripts\python.exe -m traffic_rl show --layouts intersection crossroads tjunction roundabout --scenarios balanced peak surge --seconds 300
```

首次安装见 [快速开始](docs/quickstart.md)。导出后打开 `index.html`，无需联网或再次启动 SUMO。

实验台采用单屏布局：地图、右侧信息与底部播放控制。交通演示用于观察和比较，学习模式用于逐步查看状态、动作和奖励；长内容通过分页弹窗查看。

## 文档入口

- [快速开始](docs/quickstart.md)：安装、演示、离线分享。
- [项目结构](docs/architecture.md)：目录职责与团队分工。
- [学习指南](docs/learning.md)：状态、动作、奖励和道路区别。
- [实验指南](docs/experiments.md)：训练、评估、指标与测试。

配置位于 `configs/`，代码位于 `traffic_rl/`，测试位于 `tests/`。生成路网与实验产物分别存放在 `data/generated/` 和 `outputs/`，不上传仓库。

本项目使用合成车流；短程模型只验证训练流程，不代表策略已经收敛。环岛目前为单车道逆时针通行。
