"""Locate the project-local SUMO distribution without changing system settings."""
from __future__ import annotations

import json
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
    os.environ["PATH"] = str(home / "bin") + os.pathsep + os.environ.get("PATH", "")
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
    delta = sim["delta_time"]
    if delta <= 0 or not 0 < sim["yellow_time"] < delta:
        raise ValueError("SUMO-RL requires 0 < yellow_time < delta_time.")
    for key in ("duration_seconds", "min_green", "max_green", "fixed_green"):
        if sim[key] <= 0 or sim[key] % delta:
            raise ValueError(f"{key} must be a positive multiple of delta_time.")
    if not sim["min_green"] <= sim["fixed_green"] <= sim["max_green"]:
        raise ValueError("Require min_green <= fixed_green <= max_green.")
    for name, rates in config["demand_vehicles_per_hour_per_approach"].items():
        if set(rates) != {"N", "S", "E", "W"} or any(rate < 0 for rate in rates.values()):
            raise ValueError(f"Invalid approach demand for {name}.")
    return config


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
