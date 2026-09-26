from __future__ import annotations
import hashlib
import json
from pathlib import Path
from ..common.runtime import ROOT, binary, read_config, save_json
from ..common.artifacts import output_dir, versions
def evaluate(args, config):
    from ..envs.factory import make_env, validate_model
    from ..experiments.metrics import episode_metrics, write_csv
    from ..networks.scenario import routes

    run = output_dir(args.out, "eval")
    policies = args.policies
    if "dqn" in policies and not args.model:
        raise ValueError("--model is required for the dqn policy.")
    model = None
    if "dqn" in policies:
        import torch
        from ..agents.dqn import load_model
        torch.set_num_threads(2)
        model = load_model(args.model)
    scenarios = args.scenarios or config["evaluation"]["scenarios"]
    seeds = args.seeds or config["evaluation"]["seeds"]
    summary = []
    demand_hashes = {}
    for scenario in scenarios:
        for seed in seeds:
            route_file, _ = routes(config, scenario, seed)
            demand_hashes[f"{scenario}/{seed}"] = hashlib.sha256(route_file.read_bytes()).hexdigest()
            for policy in policies:
                case = run / f"{scenario}_{seed}_{policy}"
                tripinfo = case / "tripinfo.xml"
                env = make_env(config, scenario, seed, gui=args.gui, gui_delay=args.gui_delay, tripinfo=tripinfo)
                trace = []
                try:
                    validate_model(model, env)
                    obs, _ = env.reset(seed=seed)
                    done = False
                    while not done:
                        action = int(model.predict(obs, deterministic=True)[0]) if policy == "dqn" else env.baseline_action(policy)
                        obs, reward, terminated, truncated, info = env.step(action)
                        trace.append(info | {"reward": reward})
                        done = terminated or truncated
                    if args.gui and not args.no_gui_pause:
                        print("Simulation complete. Window remains open. Press Enter in this terminal to close it and save results.", flush=True)
                        try:
                            input()
                        except EOFError:
                            print("No interactive input available; closing the window and saving results.", flush=True)
                finally:
                    env.close()  # Flush unfinished trip records before parsing.
                metrics = episode_metrics(tripinfo, route_file, config["simulation"]["duration_seconds"], trace)
                row = {"layout": config.get("layout", "intersection"), "scenario": scenario, "seed": seed, "policy": policy, **metrics}
                summary.append(row)
                write_csv(case / "trace.csv", trace)
                save_json(case / "metrics.json", row)
                print(f"{scenario} seed={seed} {policy}: mean wait+entry delay={metrics['mean_wait_plus_entry_delay_all_s']:.2f}s, completed={metrics['completed_vehicles']}/{metrics['planned_vehicles']}", flush=True)
    write_csv(run / "summary.csv", summary)
    model_path = Path(args.model).resolve() if args.model else None
    save_json(run / "run.json", {"kind": "evaluation", "config": config, "policies": policies, "scenarios": scenarios, "seeds": seeds, "demand_sha256": demand_hashes, "model": str(model_path) if model_path else None, "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest() if model_path else None, "packages": versions(), "note": "Synthetic, uncalibrated traffic. End-of-horizon unfinished trips are included; waits are observed up to the horizon, not full future waits."})
    lines = ["# 评估结果", "", "数据来源：人工设定的泊松到达车流，尚未用真实路口观测校准。", "", "以下为各次仿真结果；短程 DQN 仅用于检查流程，不表示算法已收敛。", "", "| 场景 | 随机种子 | 策略 | 平均等待＋入网延迟（秒） | 完成/计划车辆 | 未入网 |", "|---|---:|---|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| {row['scenario']} | {row['seed']} | {row['policy']} | {row['mean_wait_plus_entry_delay_all_s']:.2f} | {row['completed_vehicles']}/{row['planned_vehicles']} | {row['not_inserted_vehicles']} |")
    lines.extend(["", "指标定义见 docs/experiments.md。不同策略使用相同到达记录；正式报告需要多个训练种子和独立测试车流。"])
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Evaluation saved: {run}", flush=True)
