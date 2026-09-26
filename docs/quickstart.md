# 快速开始

在项目根目录运行 PowerShell。已有 `.venv` 时跳过安装。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m traffic_rl doctor
```

打开单屏实验台：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl show --layouts intersection crossroads tjunction roundabout --scenarios balanced peak surge --seconds 300
```

首次导出会运行 SUMO。完成后自动打开页面；之后双击输出目录中的 `index.html` 即可离线回放。分享时保留整个文件夹。

- **交通演示**：选择道路、车流、策略；右侧切换当前路况与整段结果。
- **学习模式**：上一步 / 下一步查看已完成决策；初始时刻不提前显示奖励。
- **更多信息**：状态向量、实验参数和使用说明采用分页弹窗。
- **视图**：拖动平移、滚轮缩放、复位；播放倍速不改变仿真结果。

界面以 2560×1440 屏幕为主要目标，同时适配系统缩放后的桌面窗口。较矮窗口中，状态、动作、奖励切换查看，页面不滚动。

已有历史回放可直接更新展示界面，无需再次仿真：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl.replay.package --source outputs/旧回放目录 --out outputs/新回放目录
```

`--out` 使用新目录，避免覆盖已有实验。训练与评估见 [实验指南](experiments.md)。
