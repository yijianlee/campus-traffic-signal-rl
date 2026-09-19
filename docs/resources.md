# 已采用的资源与环境记录

核查日期：2026-09-19。优先使用项目作者、官方文档和可安装发行版。

| 资源 | 本项目用途 | 已安装版本 | 官方来源 |
|---|---|---|---|
| Eclipse SUMO | 微观交通仿真、netconvert、可选 GUI | 1.27.1 | https://eclipse.dev/sumo/docs/Downloads.html |
| TraCI / sumolib | Python 与 SUMO 通信、工具定位 | 1.27.1 | https://sumo.dlr.de/docs/TraCI.html |
| SUMO-RL | Gymnasium 单路口接口、相位转换和观测 | 1.4.5 | https://github.com/LucasAlegre/sumo-rl |
| Stable-Baselines3 | DQN 训练、模型保存和读取 | 2.9.0 | https://stable-baselines3.readthedocs.io/en/master/modules/dqn.html |
| Gymnasium | 状态、动作与环境接口 | 1.3.0 | https://gymnasium.farama.org/ |
| PyTorch | 神经网络计算 | 本机已有 2.14.0+cu130 | https://pytorch.org/ |

车流生成方法参考 SUMO 的需求建模概念：https://sumo.dlr.de/docs/Demand/Introduction_to_demand_modelling_in_SUMO.html 。本项目没有复制真实路口数据，采用本地脚本生成显式车辆列表，记录参数、种子和文件 SHA-256。

SUMO 官方支持通过 `pip install eclipse-sumo` 安装 Windows 仿真程序。因此当前无需额外安装系统级 SUMO，也不依赖云平台或付费数据。下载安装使用了本机配置的 USTC PyPI 镜像。

## 已处理的实际兼容问题

- Windows 中文目录：本机 SUMO XML 加载器在 `SUMO_HOME` 包含中文绝对路径时退出。程序切换到项目根目录，使用相对 `SUMO_HOME`、相对输入和输出路径；不修改系统环境变量。
- SUMO-RL 的附加参数以空格拆分：运行输出子目录限制为不含空白字符的项目内路径；默认自动生成符合要求的名称。
- netconvert 可重排信号连接索引：路网生成后按实际连接映射生成相位，测试验证南北与东西不会同时获得绿灯。
- SUMO-RL 1.4.5 接收 `max_green`，但其 `set_next_phase` 未执行最长绿灯限制：项目包装层增加了强制切换，并在逐秒仿真测试中验证黄灯时长和绿灯上界。
- 配置要求 `delta_time > yellow_time`。初始为 5 秒和 3 秒，控制时刻取整的影响已在 README 说明。

## 环境复现

`requirements.txt` 固定核心仿真与 RL 库版本；PyTorch、NumPy 的版本范围允许在其他电脑安装。当前环境复用了已有系统包，因此它不是完全封闭的锁定环境。

每个训练/评估目录中的 `run.json` 记录实际核心包版本；`outputs/environment_check.json` 记录 Python、系统、GPU 与真实仿真连接结果。要在另一台机器严格复现，应按这些记录建立干净环境，同时匹配操作系统与硬件相关依赖。
