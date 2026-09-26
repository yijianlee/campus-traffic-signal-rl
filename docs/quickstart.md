# 快速开始

在项目根目录打开 PowerShell。

首次安装：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m traffic_rl doctor
```

完整课程实验：

```powershell
.\.venv\Scripts\python.exe -m traffic_rl train --steps 30000 --out outputs/my_model
.\.venv\Scripts\python.exe -m traffic_rl evaluate --model outputs/my_model/model.zip --out outputs/my_evaluation
.\.venv\Scripts\python.exe -m traffic_rl show --model outputs/my_model/model.zip --out outputs/my_demo
```

先验证流程可用 `train --steps 3000 --seconds 600`，并在 evaluate/show 中同样传入 `--seconds 600`。短训练不代表模型已经学好。每次实验使用新输出目录，避免混淆或覆盖结果。

本机本次已生成 `outputs/course_dqn`、`outputs/course_evaluation`、`outputs/course_demo`，分别为短训练、独立测试与展示。它们不随 Git 克隆分发。

已有演示无需重新仿真：

```powershell
.\.venv\Scripts\python.exe -m http.server 8769 --bind 127.0.0.1 --directory outputs/course_demo
```

访问 http://127.0.0.1:8769/，终端保持开启；Ctrl+C 停止服务。也可用普通浏览器打开导出目录的 index.html，分享时保留整个文件夹。

页面仅有十字路口综合车流与 DQN。交通演示查看路况；学习模式用下一步查看真实的状态、动作和奖励。播放不会训练模型。界面适配 2K 单屏，小窗口中学习内容通过标签切换。
