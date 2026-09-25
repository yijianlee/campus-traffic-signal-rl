"""Seeded turning traffic and three real SUMO road topologies."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import xml.etree.ElementTree as ET

from .runtime import ROOT, binary, save_json
from .scenario import DIRECTIONS, OPPOSITE, write_xml

LAYOUTS = ("crossroads", "tjunction", "roundabout")
SCENARIOS = ("balanced", "peak", "tidal", "surge")
RING = ("N", "W", "S", "E")  # Counterclockwise, right-hand traffic.
VECTORS = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def directions(layout):
    return tuple(d for d in DIRECTIONS if layout != "tjunction" or d != "N")


def network(config):
    layout = config["layout"]
    if layout not in LAYOUTS:
        raise ValueError("A concrete layout is required to generate a network.")
    sim = config["simulation"]
    signature = hashlib.sha256(json.dumps([layout, sim["road_length_m"], sim["speed_limit_mps"], 3]).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"{layout}_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "network.net.xml"
    if target.exists():
        return target
    nodes, edges, links = ET.Element("nodes"), ET.Element("edges"), ET.Element("connections")

    def node(name, x, y, kind="priority"):
        ET.SubElement(nodes, "node", id=name, x=str(x), y=str(y), type=kind)

    def edge(name, start, end, priority=1, shape=None):
        attrs = {"id": name, "from": start, "to": end, "numLanes": "1", "priority": str(priority), "speed": str(min(sim["speed_limit_mps"], 8.33) if name.startswith("ring_") else sim["speed_limit_mps"])}
        if shape:
            attrs["shape"] = shape
        ET.SubElement(edges, "edge", attrs)

    def connect(start, end):
        ET.SubElement(links, "connection", {"from": start, "to": end, "fromLane": "0", "toLane": "0"})

    if layout != "roundabout":
        node("J", 0, 0, "traffic_light")
    for d in directions(layout):
        x, y = VECTORS[d]
        node(d, x * sim["road_length_m"], y * sim["road_length_m"])
        if layout == "roundabout":
            node(f"R_{d}", x * 26, y * 26)
            node(f"M_{d}", x * 48, y * 48, "traffic_light")
            edge(f"{d}_in", d, f"M_{d}")
            edge(f"{d}_entry", f"M_{d}", f"R_{d}")
            edge(f"{d}_out", f"R_{d}", d)
            connect(f"{d}_in", f"{d}_entry")
        else:
            edge(f"{d}_in", d, "J")
            edge(f"{d}_out", "J", d)
    if layout == "roundabout":
        for i, d in enumerate(RING):
            destination = RING[(i + 1) % 4]
            points = [(26 * math.cos(math.radians(90 + i * 90 + a)), 26 * math.sin(math.radians(90 + i * 90 + a))) for a in range(0, 91, 5)]
            edge(f"ring_{d}", f"R_{d}", f"R_{destination}", 3, " ".join(f"{x:.3f},{y:.3f}" for x, y in points))
            connect(f"{d}_entry", f"ring_{d}")
            connect(f"ring_{RING[(i - 1) % 4]}", f"ring_{d}")
            connect(f"ring_{RING[(i - 1) % 4]}", f"{d}_out")
        ET.SubElement(edges, "roundabout", edges=" ".join(f"ring_{d}" for d in RING), nodes=" ".join(f"R_{d}" for d in RING))
    else:
        for d in directions(layout):
            for destination in directions(layout):
                if destination != d:
                    connect(f"{d}_in", f"{destination}_out")
    for name, root in (("nodes.xml", nodes), ("edges.xml", edges), ("links.xml", links)):
        write_xml(folder / name, root)
    process_env = os.environ.copy()
    command = [binary("netconvert"), "--node-files", "nodes.xml", "--edge-files", "edges.xml", "--connection-files", "links.xml", "--output-file", target.name, "--no-turnarounds", "true", "--xml-validation", "never"]
    process_env.pop("SUMO_HOME", None)
    result = subprocess.run(command, cwd=folder, env=process_env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return target


def routes(config, scenario, seed):
    layout = config["layout"]
    rates = config["demand_vehicles_per_hour_per_approach"].get(scenario)
    if rates is None and scenario == "surge":
        rates = dict.fromkeys(DIRECTIONS, 300)
    if rates is None:
        raise ValueError(f"Unknown scenario: {scenario}")
    duration = config["simulation"]["duration_seconds"]
    signature = hashlib.sha256(json.dumps([layout, rates, duration, seed, scenario, 2], sort_keys=True).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"turning_demand_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "vehicles.rou.xml"
    rng = random.Random(seed)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="car", accel="2.6", decel="4.5", sigma="0.5", length="5", minGap="2.5", maxSpeed=str(config["simulation"]["speed_limit_mps"]))
    arrivals = []
    for d in directions(layout):
        destinations = [v for v in directions(layout) if v != d]
        for dest in destinations:
            path = [f"{d}_in"]
            if layout == "roundabout":
                path.append(f"{d}_entry")
                i = RING.index(d)
                while True:
                    path.append(f"ring_{RING[i]}")
                    i = (i + 1) % 4
                    if RING[i] == dest:
                        break
            path.append(f"{dest}_out")
            ET.SubElement(root, "route", id=f"{d}_{dest}", edges=" ".join(path))
        segments = [(0, duration, 1)] if scenario != "surge" else [(0, duration / 3, 1), (duration / 3, 2 * duration / 3, 2.5), (2 * duration / 3, duration, .6)]
        count = 0
        for start, end, multiplier in segments:
            rate = rates[d] * multiplier / 3600
            if not rate:
                continue
            t = start + rng.expovariate(rate)
            while t < end:
                dest = rng.choices(destinations, weights=[2 if dest == OPPOSITE[d] else 1 for dest in destinations])[0]
                arrivals.append((t, d, count, dest))
                count += 1
                t += rng.expovariate(rate)
    for t, d, count, dest in sorted(arrivals):
        ET.SubElement(root, "vehicle", id=f"{d}_{count}", type="car", route=f"{d}_{dest}", depart=f"{t:.3f}", departLane="0", departSpeed="max")
    write_xml(target, root)
    save_json(folder / "manifest.json", {"source": "synthetic_poisson_arrivals", "field_calibrated": False, "layout": layout, "scenario": scenario, "seed": seed, "vehicles": len(arrivals), "rates_veh_per_hour": rates, "surge_multipliers": [1, 2.5, .6] if scenario == "surge" else None, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return target, len(arrivals)
