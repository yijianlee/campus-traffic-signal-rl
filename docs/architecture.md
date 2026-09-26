# 项目结构

```text
traffic_rl/
  __main__.py          兼容命令入口
  cli/                 参数解析、环境检查
  common/              配置、SUMO 运行路径、产物目录
  networks/            路网与可复现车流生成
  envs/                Gymnasium 环境、控制约束、回放适配
  agents/              固定配时、排队优先、自然让行、DQN
  experiments/         训练、评估、指标
  replay/              轨迹导出、离线分包
  web/
    index.html         单屏布局
    styles/            界面样式
    scripts/           加载、分页、渲染与交互
configs/               实验配置
tests/                 行为、路网、指标、导出测试
docs/                  当前指南；archive 保存历史资料
data/generated/        可重新生成的路网和车流，不入库
outputs/               模型、评估、回放，不入库
```

调用关系：`cli → experiments / replay → envs → networks`。策略读取状态，环境执行动作与信号约束；网页只读取导出的评估结果。

旧的 `traffic_rl.environment`、`runtime`、`scenario`、`roadnet`、`multi_environment`、`metrics`、`presentation` 保留为兼容入口，新代码使用上面的职责目录。

回放包使用小型 `recordings.js` 索引与 `recordings/run_*.js`。一次加载一个场景记录，缓存最多两份；动态脚本兼容 `file://` 离线打开。导出器仍返回完整 Python 数据，便于测试与分析。

前端地图使用 Canvas；静态道路缓存，车辆轨迹插值，绘制限制为最多 60 FPS。插值不参与指标计算。

团队分工建议：路网与环境、策略与训练、实验与报告、网页展示。修改接口后运行 `python -m unittest discover -s tests -q`，不要提交模型、生成数据或个人学习目录。
