"""Paired, held-out evaluation of DQN against fixed-time control."""
import hashlib
from pathlib import Path
import numpy as np
from .agent import load_model
from .artifacts import output_dir, versions
from .config import save_json
from .demand import routes
from .env import IntersectionEnv, validate_model
from .metrics import episode_metrics, write_csv


def evaluate(args, config):
    model = load_model(args.model)
    seeds = args.seeds or config["evaluation"]["seeds"]
    if len(set(seeds)) != len(seeds):
        raise ValueError("Evaluation seeds must be unique.")
    if any(seed >= 100000 or seed < 0 for seed in seeds):
        raise ValueError("Evaluation seeds must be in [0, 100000); training uses a separate namespace.")
    folder = output_dir(args.out, "evaluation")
    rows, hashes = [], {}
    for seed in seeds:
        route_file, _ = routes(config, seed)
        hashes[str(seed)] = hashlib.sha256(route_file.read_bytes()).hexdigest()
        for policy in ("fixed", "dqn"):
            case = folder / f"{seed}_{policy}"
            tripinfo = case / "tripinfo.xml"
            env = IntersectionEnv(config, seed, tripinfo=tripinfo)
            trace = []
            try:
                validate_model(model, env)
                obs, _ = env.reset(seed=seed)
                done = False
                while not done:
                    action = int(model.predict(obs, deterministic=True)[0]) if policy == "dqn" else env.baseline_action()
                    obs, reward, terminated, truncated, info = env.step(action)
                    trace.append(info | {"reward": reward})
                    done = terminated or truncated
            finally:
                env.close()
            metrics = episode_metrics(tripinfo, route_file, config["simulation"]["duration_seconds"], trace)
            row = {"seed": seed, "policy": policy, **metrics}
            rows.append(row)
            write_csv(case / "trace.csv", trace)
            save_json(case / "metrics.json", row)
            print(f"seed={seed} {policy}: wait={metrics['mean_wait_plus_entry_delay_all_s']:.2f}s, completed={metrics['completion_rate']:.1%}", flush=True)
    write_csv(folder / "summary.csv", rows)
    save_json(folder / "run.json", {"kind": "evaluation", "config": config, "seeds": seeds, "demand_sha256": hashes, "model": str(Path(args.model).resolve()), "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest(), "packages": versions()})
    aggregate = []
    columns = ["mean_wait_plus_entry_delay_all_s", "mean_queue_sampled", "completion_rate"]
    for policy in ("fixed", "dqn"):
        selected = [row for row in rows if row["policy"] == policy]
        item = {"policy": policy, "seeds": len(selected)}
        for column in columns:
            values = [row[column] for row in selected]
            item[column + "_mean"] = float(np.mean(values))
            item[column + "_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        aggregate.append(item)
    write_csv(folder / "aggregate.csv", aggregate)
    lines = ["# 独立车流评估", "", "同一种子下两种策略使用相同车辆到达记录。标准差反映测试车流差异，不代表不同训练模型的不确定性。", "", "| 策略 | 等待＋入网延迟（秒） | 平均队列（辆） | 完成率 |", "|---|---:|---:|---:|"]
    for row in aggregate:
        lines.append(f"| {row['policy']} | {row[columns[0]+'_mean']:.2f} ± {row[columns[0]+'_std']:.2f} | {row[columns[1]+'_mean']:.2f} ± {row[columns[1]+'_std']:.2f} | {row[columns[2]+'_mean']:.1%} ± {row[columns[2]+'_std']:.1%} |")
    lines += ["", "统计包括结束时未完成及未入网车辆，截至仿真结束。合成车流未经实地校准；DQN 不保证优于固定配时。正式课程实验建议重复多个训练种子。"]
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot_comparison(folder, aggregate, columns)
    print(f"Evaluation saved: {folder}", flush=True)
    return rows, folder


def plot_comparison(folder, rows, columns):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, column, label in zip(axes, columns, ["Wait + entry delay (s)", "Mean queue (vehicles)", "Completion rate"]):
        ax.bar(["Fixed", "DQN"], [r[column + "_mean"] for r in rows], yerr=[r[column + "_std"] for r in rows], color=["#a6b5ad", "#167a65"], capsize=5)
        ax.set_title(label); ax.set_ylim(bottom=0); ax.grid(axis="y", alpha=.15)
    fig.tight_layout(); fig.savefig(folder / "comparison.png", dpi=160); plt.close(fig)
