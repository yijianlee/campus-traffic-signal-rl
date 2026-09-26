from __future__ import annotations
import hashlib
from .config import save_json
from .agent import create_model, load_model
from .artifacts import output_dir, versions
def train(args, config):
    import torch
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor
    from .env import IntersectionEnv

    torch.set_num_threads(2)
    run = output_dir(args.out, "train")
    settings = config["training"]
    seed = args.seed if args.seed is not None else settings["seed"]
    steps = args.steps if args.steps is not None else settings["total_timesteps"]
    if steps <= settings["learning_starts"]:
        raise ValueError("Training steps must exceed learning_starts so gradient updates actually occur.")
    episode_steps = config["simulation"]["duration_seconds"] // config["simulation"]["delta_time"]
    if (steps + episode_steps - 1) // episode_steps > 1000:
        raise ValueError("This seed partition supports at most 1000 episodes per run; increase --seconds or reduce --steps.")
    raw = IntersectionEnv(config, seed, vary_demand=True)
    env = Monitor(raw, str(run / "monitor.csv"))
    try:
        model = create_model(env, settings, seed)
        model.set_logger(configure(str(run), ["stdout", "csv"]))
        before = [parameter.detach().clone() for parameter in model.q_net.parameters()]
        model.learn(total_timesteps=steps, log_interval=5)
        changed = any(not torch.equal(old, new.detach()) for old, new in zip(before, model.q_net.parameters()))
        model.save(run / "model")
        # Verify deserialization and prediction, not only successful writing.
        restored = load_model(run / "model.zip")
        prediction, _ = restored.predict(raw.observation_space.sample(), deterministic=True)
        if not changed or not raw.action_space.contains(int(prediction)):
            raise RuntimeError("Training/save/reload verification failed.")
        save_json(run / "run.json", {"kind": "training", "episodes": getattr(raw, "episodes", []), "config": config, "training_seed": seed, "first_demand_seed": 100000 + seed * 1000, "requested_steps": steps, "actual_steps": model.num_timesteps, "gradient_updates": model._n_updates, "weights_changed": changed, "save_reload_passed": True, "model_sha256": hashlib.sha256((run / "model.zip").read_bytes()).hexdigest(), "packages": versions(), "note": "A short training run validates the pipeline; it does not establish policy quality."})
    finally:
        env.close()
    plot_training(run)
    print(f"Training saved: {run}", flush=True)


def plot_training(folder):
    """Raw episode returns and a trailing mean; not an evaluation score."""
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with (folder / "monitor.csv").open(encoding="utf-8") as handle:
        next(handle)
        rows = list(csv.DictReader(handle))
    if not rows:
        return
    rewards = [float(row["r"]) for row in rows]
    steps = np.cumsum([int(row["l"]) for row in rows])
    smooth = [np.mean(rewards[max(0, i-9):i+1]) for i in range(len(rewards))]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(steps, rewards, color="#aacbbc", alpha=.7, label="Episode return")
    ax.plot(steps, smooth, color="#167a65", label="Trailing mean (up to 10 episodes)")
    ax.set(xlabel="Training steps", ylabel="Return", title="DQN training on composite traffic")
    ax.legend(); ax.grid(alpha=.15); fig.tight_layout()
    fig.savefig(folder / "learning_curve.png", dpi=160)
    plt.close(fig)
