"""Episode metrics with unfinished trips and entry backlog explicitly included."""
from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def episode_metrics(tripinfo: Path, route_file: Path, duration: int, trace: list[dict]) -> dict:
    schedule = {v.attrib["id"]: float(v.attrib["depart"]) for v in ET.parse(route_file).getroot().findall("vehicle") if float(v.attrib["depart"]) < duration}
    trips = [v.attrib for v in ET.parse(tripinfo).getroot().findall("tripinfo") if float(v.get("depart", "-1")) >= 0]
    by_id = {v["id"]: v for v in trips}
    pending = set(schedule) - set(by_id)
    completed = sum(float(v["arrival"]) >= 0 for v in trips)
    unfinished = len(trips) - completed
    waits = [float(v["waitingTime"]) for v in trips]
    # This is stopped time + insertion delay, not travel time or SUMO timeLoss.
    costs = {vid: float(v["waitingTime"]) + float(v["departDelay"]) for vid, v in by_id.items()}
    costs.update({vid: max(0.0, duration - schedule[vid]) for vid in pending})
    if set(costs) != set(schedule):
        raise RuntimeError("Trip report and scheduled demand do not reconcile.")
    mean = lambda values: float(np.mean(values)) if values else 0.0
    result = {
        "planned_vehicles": len(schedule), "departed_vehicles": len(trips),
        "completed_vehicles": completed, "unfinished_vehicles": unfinished,
        "not_inserted_vehicles": len(pending),
        "completion_rate": completed / len(schedule) if schedule else 0.0,
        "mean_stopped_wait_departed_s": mean(waits),
        "p95_stopped_wait_departed_s": float(np.percentile(waits, 95)) if waits else 0.0,
        "mean_wait_plus_entry_delay_all_s": mean(list(costs.values())),
        "mean_queue_sampled": mean([row["queue_total"] for row in trace]),
        "max_queue_sampled": max((row["queue_total"] for row in trace), default=0),
        "switches": sum(row["switched"] for row in trace),
        "forced_switches": sum(row["forced_switch"] for row in trace),
    }
    for direction in "NSEW":
        result[f"mean_wait_plus_entry_delay_{direction}_s"] = mean([cost for vid, cost in costs.items() if vid.startswith(direction + "_")])
    if trace and "collisions" in trace[-1]:
        result["collision_vehicle_events"] = trace[-1]["collisions"]
        result["teleport_events"] = trace[-1]["teleports"]
    return result
