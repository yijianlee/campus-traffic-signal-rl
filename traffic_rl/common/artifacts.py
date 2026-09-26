"""Output folders and dependency provenance."""
import importlib.metadata
from datetime import datetime
from pathlib import Path
from .runtime import ROOT

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
