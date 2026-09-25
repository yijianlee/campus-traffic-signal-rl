"""Run with .venv\\Scripts\\python.exe -m traffic_rl --help."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from .runtime import ROOT, binary, read_config, save_json


def output_dir(value: str | None, prefix: str) -> Path:
    relative = value or f"outputs/{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT)
    if any(c.isspace() for c in path.relative_to(ROOT).as_posix()):
        raise ValueError("Output directory names must not contain whitespace.")
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"Refusing to overwrite an existing run: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def versions() -> dict:
    names = ["eclipse-sumo", "sumo-data", "traci", "sumolib", "sumo-rl", "stable-baselines3", "gymnasium", "numpy", "torch", "pandas", "pettingzoo"]
    return {name: importlib.metadata.version(name) for name in names}


def doctor(args, config):
    import torch
    info = {"python": platform.python_version(), "platform": platform.platform(), "packages": versions(), "cuda_available": torch.cuda.is_available(), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "sumo_binary": binary("sumo")}
    subprocess.run([binary("sumo"), "--version"], check=True, capture_output=True)
    from .multi_environment import make_env, validate_model
    env = make_env(config, "balanced", 101)
    try:
        observation, _ = env.reset(seed=101)
        _, reward, _, _, _ = env.step(0)
        info.update({"observation_shape": list(observation.shape), "actions": int(env.action_space.n), "first_reward": reward, "simulation_connection": "passed"})
    finally:
        env.close()
    save_json(ROOT / "outputs/environment_check.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def train(args, config):
    import torch
    from stable_baselines3 import DQN
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor
    from .multi_environment import make_env, validate_model

    torch.set_num_threads(2)
    run = output_dir(args.out, "train")
    settings = config["training"]
    seed = args.seed if args.seed is not None else settings["seed"]
    steps = args.steps if args.steps is not None else settings["total_timesteps"]
    if steps <= settings["learning_starts"]:
        raise ValueError("Training steps must exceed learning_starts so gradient updates actually occur.")
    scenario = args.scenario or settings["scenario"]
    raw = make_env(config, scenario, seed, vary_demand=True)
    env = Monitor(raw, str(run / "monitor.csv"))
    params = {key: settings[key] for key in ("learning_rate", "buffer_size", "learning_starts", "batch_size", "gamma", "train_freq", "target_update_interval", "exploration_fraction", "exploration_final_eps", "device")}
    try:
        model = DQN("MlpPolicy", env, seed=seed, verbose=1, policy_kwargs={"net_arch": settings["net_arch"]}, **params)
        model.set_logger(configure(str(run), ["stdout", "csv"]))
        before = [parameter.detach().clone() for parameter in model.q_net.parameters()]
        model.learn(total_timesteps=steps, log_interval=5)
        changed = any(not torch.equal(old, new.detach()) for old, new in zip(before, model.q_net.parameters()))
        model.save(run / "model")
        # Verify deserialization and prediction, not only successful writing.
        restored = DQN.load(run / "model.zip", device="cpu")
        prediction, _ = restored.predict(raw.observation_space.sample(), deterministic=True)
        if not changed or not raw.action_space.contains(int(prediction)):
            raise RuntimeError("Training/save/reload verification failed.")
        save_json(run / "run.json", {"kind": "training", "episodes": getattr(raw, "episodes", []), "config": config, "scenario": scenario, "training_seed": seed, "first_demand_seed": 100000 + seed * 1000, "requested_steps": steps, "actual_steps": model.num_timesteps, "gradient_updates": model._n_updates, "weights_changed": changed, "save_reload_passed": True, "model_sha256": hashlib.sha256((run / "model.zip").read_bytes()).hexdigest(), "packages": versions(), "note": "A short training run validates the pipeline; it does not establish policy quality."})
    finally:
        env.close()
    print(f"Training saved: {run}", flush=True)


def evaluate(args, config):
    from .multi_environment import make_env, validate_model
    from .metrics import episode_metrics, write_csv
    from .scenario import routes

    run = output_dir(args.out, "eval")
    policies = args.policies
    if "dqn" in policies and not args.model:
        raise ValueError("--model is required for the dqn policy.")
    model = None
    if "dqn" in policies:
        import torch
        from stable_baselines3 import DQN
        torch.set_num_threads(2)
        model = DQN.load(args.model, device="cpu")
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
    lines.extend(["", "指标定义见 docs/experiment_plan.md。不同策略使用相同到达记录；正式报告需要多个训练种子和独立测试车流。"])
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Evaluation saved: {run}", flush=True)


def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description="Campus Traffic Signal RL")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check packages, SUMO and Gymnasium connection")
    build = sub.add_parser("build", help="Generate network and evaluation demand")
    show = sub.add_parser("show", help="Build and open the polished offline traffic presentation")
    show.add_argument("--seconds", type=int, default=300)
    show.add_argument("--seed", type=int, default=101)
    show.add_argument("--scenarios", nargs="+", choices=["balanced", "peak", "tidal", "surge"], default=["balanced", "peak", "tidal"])
    show.add_argument("--model", help="Optional DQN model to include in the strategy switcher")
    show.add_argument("--out", help="New output directory under the project")
    show.add_argument("--no-open", action="store_true", help="Export without opening a browser")
    training = sub.add_parser("train", help="Train and verify DQN")
    training.add_argument("--steps", type=int)
    training.add_argument("--seed", type=int)
    training.add_argument("--scenario", choices=["balanced", "peak", "tidal", "surge", "mixed"])
    evaluation = sub.add_parser("evaluate", help="Evaluate policies on identical traffic")
    evaluation.add_argument("--policies", nargs="+", choices=["fixed", "queue", "dqn", "yield"], default=["fixed", "queue"])
    evaluation.add_argument("--scenarios", nargs="+", choices=["balanced", "peak", "tidal", "surge"])
    evaluation.add_argument("--seeds", nargs="+", type=int)
    evaluation.add_argument("--model")
    evaluation.add_argument("--gui", action="store_true", help="Open SUMO GUI for each episode")
    evaluation.add_argument("--gui-delay", type=int, default=100, metavar="MS", help="GUI delay per simulation second in milliseconds (default: 100; 0: fastest)")
    evaluation.add_argument("--no-gui-pause", action="store_true", help="Close GUI automatically at the end instead of waiting for Enter")
    for item in (build, training, evaluation):
        item.add_argument("--seconds", type=int, help="Override episode length in simulated seconds")
    for item in (training, evaluation):
        item.add_argument("--out", help="New output directory under the project; omit for timestamped directory")
    for item in (build, show, training, evaluation):
        item.add_argument("--layout", choices=["intersection", "crossroads", "tjunction", "roundabout"] + (["mixed"] if item is training else []), help="Road topology; mixed randomizes topology each training episode")
    args = parser.parse_args()
    if getattr(args, "gui_delay", 0) < 0:
        parser.error("--gui-delay must be nonnegative")
    config = read_config(args.config)
    if getattr(args, "layout", None):
        config["layout"] = args.layout
    layout = config.get("layout", "intersection")
    if layout == "mixed" and args.command != "train":
        parser.error("Select a concrete --layout for evaluation, export or build")
    requested_scenarios = ([args.scenario or config["training"]["scenario"]] if args.command == "train" else getattr(args, "scenarios", None) or config["evaluation"]["scenarios"])
    if layout == "intersection" and any(s in ("mixed", "surge") for s in requested_scenarios):
        parser.error("surge/mixed demand requires --layout crossroads, tjunction, roundabout or mixed")
    if "yield" in getattr(args, "policies", []) and layout != "roundabout":
        parser.error("--policies yield requires --layout roundabout")
    if getattr(args, "seconds", None) is not None:
        if args.seconds <= 0 or args.seconds % config["simulation"]["delta_time"]:
            parser.error("--seconds must be positive and divisible by delta_time")
        config["simulation"]["duration_seconds"] = args.seconds
    if args.command == "doctor":
        doctor(args, config)
    elif args.command == "build":
        from .scenario import network, routes
        print(network(config))
        for scenario in config["evaluation"]["scenarios"]:
            for seed in config["evaluation"]["seeds"]:
                path, count = routes(config, scenario, seed)
                print(scenario, seed, count, path)
    elif args.command == "show":
        from .presentation import present
        present(args, config)
    elif args.command == "train":
        train(args, config)
    else:
        evaluate(args, config)


if __name__ == "__main__":
    main()
