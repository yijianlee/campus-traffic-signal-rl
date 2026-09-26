"""Generate an original road network and seeded, explicit vehicle arrivals."""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from ..common.runtime import ROOT, binary, save_json

DIRECTIONS = ("N", "S", "E", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}


def write_xml(path: Path, root: ET.Element) -> None:
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def network(config: dict) -> Path:
    if config.get("layout", "intersection") != "intersection":
        from ..networks.roadnet import network as road_network
        return road_network(config)
    sim = config["simulation"]
    signature = hashlib.sha256(json.dumps({"length": sim["road_length_m"], "speed": sim["speed_limit_mps"], "version": 2}, sort_keys=True).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"network_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "intersection.net.xml"
    if target.exists():
        return target
    length = sim["road_length_m"]
    nodes = ET.Element("nodes")
    ET.SubElement(nodes, "node", id="J", x="0", y="0", type="traffic_light")
    for direction, x, y in (("N", 0, length), ("S", 0, -length), ("E", length, 0), ("W", -length, 0)):
        ET.SubElement(nodes, "node", id=direction, x=str(x), y=str(y), type="priority")
    edges = ET.Element("edges")
    connections = ET.Element("connections")
    for index, direction in enumerate(DIRECTIONS):
        ET.SubElement(edges, "edge", {"id": f"{direction}_in", "from": direction, "to": "J", "numLanes": "1", "speed": str(sim["speed_limit_mps"])})
        ET.SubElement(edges, "edge", {"id": f"{direction}_out", "from": "J", "to": direction, "numLanes": "1", "speed": str(sim["speed_limit_mps"])})
        ET.SubElement(connections, "connection", {"from": f"{direction}_in", "to": f"{OPPOSITE[direction]}_out", "fromLane": "0", "toLane": "0", "tl": "J", "linkIndex": str(index)})
    tls = ET.Element("additional")
    logic = ET.SubElement(tls, "tlLogic", id="J", type="static", programID="0", offset="0")
    for state, duration in (("GGrr", 30), ("yyrr", 5), ("rrGG", 30), ("rryy", 5)):
        ET.SubElement(logic, "phase", duration=str(duration), state=state)
    for name, root in (("nodes.nod.xml", nodes), ("edges.edg.xml", edges), ("connections.con.xml", connections), ("signals.tll.xml", tls)):
        write_xml(folder / name, root)
    # Relative paths avoid a Windows SUMO XML loader issue with Chinese paths.
    command = [binary("netconvert"), "--node-files", "nodes.nod.xml", "--edge-files", "edges.edg.xml", "--connection-files", "connections.con.xml", "--tllogic-files", "signals.tll.xml", "--output-file", target.name, "--no-turnarounds", "true", "--xml-validation", "never"]
    process_env = os.environ.copy()
    process_env.pop("SUMO_HOME", None)
    result = subprocess.run(command, cwd=folder, env=process_env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"netconvert failed:\n{result.stdout}\n{result.stderr}")
    # netconvert may renumber controlled links clockwise. Build green states
    # from the actual mapping; never assume XML input linkIndex was retained.
    net = ET.parse(target).getroot()
    links = {int(link.attrib["linkIndex"]): link.attrib["from"][0] for link in net.findall("connection") if link.get("tl") == "J"}
    if set(links) != set(range(4)) or set(links.values()) != set(DIRECTIONS):
        raise RuntimeError(f"Unexpected junction connections: {links}")
    logic = net.find("tlLogic")
    for phase, active, color in zip(logic.findall("phase"), ("NS", "NS", "EW", "EW"), ("G", "y", "G", "y")):
        phase.set("state", "".join(color if links[i] in active else "r" for i in range(4)))
    write_xml(target, net)
    return target


def routes(config: dict, scenario: str, seed: int) -> tuple[Path, int]:
    if config.get("layout", "intersection") != "intersection":
        from ..networks.roadnet import routes as turning_routes
        return turning_routes(config, scenario, seed)
    if scenario in ("surge", "mixed"):
        raise ValueError("surge/mixed demand requires a new road layout.")
    rates = config["demand_vehicles_per_hour_per_approach"][scenario]
    duration = config["simulation"]["duration_seconds"]
    signature = hashlib.sha256(json.dumps({"rates": rates, "duration": duration, "seed": seed, "version": 1}, sort_keys=True).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"demand_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "vehicles.rou.xml"
    manifest = folder / "manifest.json"
    if target.exists() and manifest.exists():
        return target, json.loads(manifest.read_text(encoding="utf-8"))["vehicles"]
    rng = random.Random(seed)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="car", accel="2.6", decel="4.5", sigma="0.5", length="5", minGap="2.5", maxSpeed="11.11")
    arrivals = []
    for direction in DIRECTIONS:
        ET.SubElement(root, "route", id=direction, edges=f"{direction}_in {OPPOSITE[direction]}_out")
        if rates[direction] == 0:
            continue
        time = rng.expovariate(rates[direction] / 3600)
        count = 0
        while time < duration:
            arrivals.append((time, direction, count))
            count += 1
            time += rng.expovariate(rates[direction] / 3600)
    for time, direction, count in sorted(arrivals):
        ET.SubElement(root, "vehicle", id=f"{direction}_{count}", type="car", route=direction, depart=f"{time:.3f}", departLane="0", departSpeed="max")
    write_xml(target, root)
    save_json(manifest, {"source": "synthetic_poisson_arrivals", "field_calibrated": False, "scenario": scenario, "seed": seed, "duration_seconds": duration, "rates_veh_per_hour": rates, "vehicles": len(arrivals), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return target, len(arrivals)
