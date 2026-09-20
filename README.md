# Campus Traffic Signal RL

A reproducible reinforcement learning project for traffic signal control at a single campus-area intersection.

Repository: `campus-traffic-signal-rl`

课程项目初始配置，2026-09-19。

**拟研究的问题：在车流变化时，强化学习能否降低车辆等待，同时避免少数方向长时间得不到放行？**

当前已经配置本地 Python 环境、SUMO 路口仿真、固定配时与排队优先基线、DQN 训练和统一评估流程。当前路口与车流均为人工构造，尚未采集或校准真实路口数据。

本次安装、验证与交付记录见 [初步配置说明](docs/initial_setup.md)。运行结果保存在本地 `outputs/`；该目录不上传 GitHub，在新电脑上运行评估命令即可生成报告。

## 先运行起来

### 精美交通演示页面（推荐课堂展示）

```powershell
.\.venv\Scripts\python.exe -m traffic_rl show
```

先在后台运行 SUMO，记录三种车流下的固定配时和排队优先策略，再自动打开中文浏览器演示页面。页面包含校园路口俯视图、平滑车辆动画、信号灯、方向队列、实时车速和整段结果，支持策略切换、1–5 倍播放、暂停、拖动进度、缩放与专注演示。默认每段记录 300 秒仿真。

要加入自己的 DQN 模型：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl show --seconds 600 --model outputs/dqn_smoke/model.zip
```

这里的模型路径仅适用于本机已有短程模型；新克隆的仓库请使用实际训练得到的模型路径。DQN 是否训练充分会影响策略表现，页面不会预设它优于基线。

生成结果位于命令打印的 `outputs/presentation_.../index.html`。之后直接双击该文件即可回放，无需再次启动 SUMO，也无需联网或安装 Node.js。分享时应保留整个输出文件夹，至少包含 `index.html`、`style.css`、`app.js`、`recordings.js`；用 `--no-open` 可以只导出不打开浏览器。

该页面是 **SUMO 实际轨迹回放**，不是在线控制或实时训练。切换策略读取相同到达记录的另一段仿真，保留当前时间。指标基于记录采样，动画在采样之间插值；校园楼宇和绿化仅作示意，不代表真实地理位置或已模拟行人。底部指标明确为整段结果，右侧为当前回放状态。当前车速按路网中所有车辆计算，进口排队为四条进口车道速度低于 0.1 m/s 的车辆数。

### 命令行与原生 SUMO 界面

在本目录打开 PowerShell，直接调用项目 Python，无需激活环境。

```powershell
# 检查依赖和实际仿真连接
.\.venv\Scripts\python.exe -m traffic_rl doctor

# 生成路网和 3 类测试车流
.\.venv\Scripts\python.exe -m traffic_rl build

# 比较固定配时和排队优先策略，默认 3 场景 × 3 种子
.\.venv\Scripts\python.exe -m traffic_rl evaluate

# 正式训练的初始配置：30,000 个决策步，不保证已经收敛
.\.venv\Scripts\python.exe -m traffic_rl train
```

每次训练都会打印输出目录，其中的 `model.zip` 为模型。评估训练后的模型时，将下面的路径替换为实际文件：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl evaluate --policies fixed queue dqn --model outputs/dqn_smoke/model.zip
```

这里的 `dqn_smoke` 是本次短程流程检查的模型，**不是经过充分训练的最终模型**。

展示交通动画：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl evaluate --policies fixed --scenarios balanced --seeds 101 --seconds 600 --gui
```

该命令会打开 SUMO 窗口，默认每个仿真秒增加 100 毫秒延迟：600 秒场景约播放 1 分钟，另加计算开销。结束后保留最后画面；回到 PowerShell 按 Enter，关闭窗口并保存结果。训练默认不打开窗口。

想更慢，可在命令末尾加 `--gui-delay 300`（600 秒场景约 3 分钟）；也可以在 SUMO 界面的 Delay 控件中实时调整。`--gui-delay 1000` 约为实时速度，`--gui-delay 0` 为最快速度。需要自动关闭窗口时加 `--no-gui-pause`。批量 GUI 评估会在每回合结束时等待 Enter；无交互输入时自动关闭并保存。

车辆运动默认每 0.1 个仿真秒更新一次，红绿灯仍每 5 秒决策。`--gui-delay 300` 会换算为每个画面步骤等待 30 毫秒，避免车辆每隔 300 毫秒跳动一秒的距离。实际流畅度仍取决于渲染性能。SUMO 界面的 Delay 数值是**每个小步**的毫秒数，与命令行参数的“每仿真秒”口径不同。

训练与无界面评估也使用相同的 0.1 秒物理步长，保证两种模式可比。此改动会改变车辆跟驰与到达时刻的离散精度；早期 1 秒步长生成的结果应保留为历史记录，不与新结果直接合并，正式实验需按当前配置重新训练和评估。

## 配置与文件

| 位置 | 用途 |
|---|---|
| `configs/default.json` | 车流、信号时长、奖励权重与 DQN 参数 |
| `traffic_rl/scenario.py` | 从零生成路网和可重复的车辆到达记录 |
| `traffic_rl/environment.py` | 状态、动作、奖励和最长绿灯约束 |
| `traffic_rl/metrics.py` | 统一指标，含未完成车辆与入网积压 |
| `traffic_rl/__main__.py` | 检查、生成、训练、评估命令 |
| `data/generated/` | 自动生成的仿真输入及来源记录 |
| `data/field/README.md` | 后续实地观测表与数据说明 |
| `outputs/` | 模型、逐步队列、车辆行程、结果表和环境信息 |
| `docs/experiment_plan.md` | 实验设计、指标口径、学期安排 |
| `docs/resources.md` | 资源来源、版本与已处理的兼容问题 |

修改配置后直接重新运行。自定义配置示例：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl --config configs/default.json train --steps 10000 --seed 43
```

评估输出中：`report.md` 可直接阅读，`summary.csv` 可用 Excel 打开，`run.json` 保存配置、版本和输入文件哈希。每个场景目录还有 `trace.csv` 和 `tripinfo.xml`。

## 本机环境与重新安装

- Windows 11，Python 3.12.10，约 31.4 GiB 内存，24 个逻辑处理器。
- NVIDIA GeForce RTX 5070 Laptop GPU 可用；初始小型 DQN 默认用 CPU，降低设备依赖，后续可在配置中改为 `cuda`。
- `.venv` 通过 `--system-site-packages` 复用机器已有的 PyTorch、NumPy 和 Gymnasium；新增 SUMO、SUMO-RL、SB3 等安装在项目目录内。
- 这不是完全独立于系统包的环境。实际使用版本记录在 `outputs/environment_check.json` 和每次运行的 `run.json`。

在新电脑上可以运行 `powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Isolated`，创建独立环境并安装依赖；需要网络下载。参数 `-Isolated` 只在尚无 `.venv` 时生效，不会替换已有环境。依赖安装脚本不修改全局 Python 包。

## 实验边界

首版只有一个十字路口、每方向一条进口车道、机动车直行和南北/东西两组相位；尚无转弯、行人、非机动车或全红阶段。最小绿灯 10 秒、黄灯 3 秒、最大绿灯 60 秒只是课程仿真参数，不是实地交通工程配时结论。

每 5 秒决策一次，因此信号时长在决策网格上取整：固定策略首段绿灯 30 秒，之后约 32 秒；最大绿灯保护会提前到下一个决策点执行，不超过 60 秒。两种基线和 DQN 共用相同的执行约束。

测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

本项目可作为课程实践起点；真实路口结论需要补充观测、校准与独立验证。
