"""Reproducible composite demand: changing volume, directional bias and noise."""
import hashlib
import json
import random
import xml.etree.ElementTree as ET

from .config import ROOT, save_json
from .network import DIRECTIONS, OPPOSITE, write_xml


def profile(config, seed):
    rng = random.Random(seed)
    duration = config["simulation"]["duration_seconds"]
    settings = config["demand"]
    segments = []
    # Each episode includes light, directional, peak and recovery periods.
    for start in range(0, duration, settings["segment_seconds"]):
        progress = start / duration
        volume = 0.65 if progress < .2 else 1.0 if progress < .45 else 1.65 if progress < .7 else .8
        bias = {d: (1.5 if d in "NS" else .65) if .2 <= progress < .45
                else (1.5 if d in "EW" else .65) if progress >= .7 else 1.0 for d in DIRECTIONS}
        rates = {d: round(settings["base_rate"] * volume * bias[d]
                          * rng.uniform(1 - settings["jitter"], 1 + settings["jitter"]), 2) for d in DIRECTIONS}
        segments.append({"start": start, "end": min(duration, start + settings["segment_seconds"]), "rates": rates})
    return segments


def routes(config, seed):
    segments = profile(config, seed)
    signature = hashlib.sha256(json.dumps([segments, seed, config["simulation"]["speed_limit_mps"], 1], sort_keys=True).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"course_demand_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "vehicles.rou.xml"
    rng = random.Random(seed + 7919)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="car", accel="2.6", decel="4.5", sigma="0.5", length="5", minGap="2.5", maxSpeed=str(config["simulation"]["speed_limit_mps"]))
    arrivals = []
    for direction in DIRECTIONS:
        destinations = [d for d in DIRECTIONS if d != direction]
        for destination in destinations:
            ET.SubElement(root, "route", id=f"{direction}_{destination}", edges=f"{direction}_in {destination}_out")
        count = 0
        for segment in segments:
            rate = segment["rates"][direction] / 3600
            t = segment["start"] + rng.expovariate(rate)
            while t < segment["end"]:
                destination = rng.choices(destinations, weights=[2 if d == OPPOSITE[direction] else 1 for d in destinations])[0]
                arrivals.append((t, direction, count, destination))
                count += 1
                t += rng.expovariate(rate)
    for t, direction, count, destination in sorted(arrivals):
        ET.SubElement(root, "vehicle", id=f"{direction}_{count}", type="car", route=f"{direction}_{destination}", depart=f"{t:.3f}", departLane="0", departSpeed="max")
    write_xml(target, root)
    save_json(folder / "manifest.json", {"seed": seed, "source": "synthetic_composite_poisson", "segments": segments, "vehicles": len(arrivals), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return target, len(arrivals)
