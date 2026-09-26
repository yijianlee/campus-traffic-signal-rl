from __future__ import annotations
import hashlib
from ..common.runtime import save_json
from ..agents.dqn import create_model, load_model
from ..common.artifacts import output_dir, versions
def train(args, config):
    import torch
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor
    from ..envs.factory import make_env

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
        save_json(run / "run.json", {"kind": "training", "episodes": getattr(raw, "episodes", []), "config": config, "scenario": scenario, "training_seed": seed, "first_demand_seed": 100000 + seed * 1000, "requested_steps": steps, "actual_steps": model.num_timesteps, "gradient_updates": model._n_updates, "weights_changed": changed, "save_reload_passed": True, "model_sha256": hashlib.sha256((run / "model.zip").read_bytes()).hexdigest(), "packages": versions(), "note": "A short training run validates the pipeline; it does not establish policy quality."})
    finally:
        env.close()
    print(f"Training saved: {run}", flush=True)
