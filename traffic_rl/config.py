"""Locate the project-local SUMO distribution without changing system settings."""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_sumo() -> Path:
    import sumo

    home = Path(sumo.SUMO_HOME)
    os.chdir(ROOT)
    # SUMO's Windows XML loader fails on non-ASCII SUMO_HOME values.
    os.environ["SUMO_HOME"] = os.path.relpath(home, ROOT)
    bin_path = str(home / "bin")
    paths = os.environ.get("PATH", "").split(os.pathsep)
    if bin_path not in paths:
        os.environ["PATH"] = os.pathsep.join([bin_path, *paths])
    # We use separate TraCI connections, including for environment construction.
    os.environ.pop("LIBSUMO_AS_TRACI", None)
    return home


def binary(name: str) -> str:
    home = configure_sumo()
    path = home / "bin" / (name + (".exe" if sys.platform == "win32" else ""))
    if not path.exists():
        raise FileNotFoundError(f"SUMO binary not found: {path}")
    return str(path)


def read_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else ROOT / "configs/default.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    sim = config["simulation"]
    step_length = sim.setdefault("step_length", 0.1)
    if not 0 < step_length <= 1 or not math.isclose(1 / step_length, round(1 / step_length)):
        raise ValueError("step_length must evenly divide one second (for example 0.1, 0.2, 0.5, 1).")
    delta = sim["delta_time"]
    if int(delta) != delta or int(sim["yellow_time"]) != sim["yellow_time"]:
        raise ValueError("delta_time and yellow_time must be whole simulation seconds.")
    if delta <= 0 or not 0 < sim["yellow_time"] < delta:
        raise ValueError("Require 0 < yellow_time < delta_time.")
    for key in ("duration_seconds", "min_green", "max_green", "fixed_green"):
        if sim[key] <= 0 or sim[key] % delta:
            raise ValueError(f"{key} must be a positive multiple of delta_time.")
    if not sim["min_green"] <= sim["fixed_green"] <= sim["max_green"]:
        raise ValueError("Require min_green <= fixed_green <= max_green.")
    demand = config["demand"]
    if demand["base_rate"] <= 0 or demand["segment_seconds"] <= 0:
        raise ValueError("Demand rate and segment duration must be positive.")
    if not 0 <= demand["jitter"] < 1:
        raise ValueError("Demand jitter must be in [0, 1).")
    if sim["road_length_m"] <= 60 or sim["speed_limit_mps"] <= 0:
        raise ValueError("Invalid road dimensions or speed.")
    return config


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
