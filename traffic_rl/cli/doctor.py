from __future__ import annotations
from ..common.runtime import ROOT, binary, save_json
from ..common.artifacts import versions
import json
import platform
import subprocess
def doctor(args, config):
    import torch
    info = {"python": platform.python_version(), "platform": platform.platform(), "packages": versions(), "cuda_available": torch.cuda.is_available(), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "sumo_binary": binary("sumo")}
    subprocess.run([binary("sumo"), "--version"], check=True, capture_output=True)
    from ..envs.factory import make_env
    env = make_env(config, "balanced", 101)
    try:
        observation, _ = env.reset(seed=101)
        _, reward, _, _, _ = env.step(0)
        info.update({"observation_shape": list(observation.shape), "actions": int(env.action_space.n), "first_reward": reward, "simulation_connection": "passed"})
    finally:
        env.close()
    save_json(ROOT / "outputs/environment_check.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=2))
