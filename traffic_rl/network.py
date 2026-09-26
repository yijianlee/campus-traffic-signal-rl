"""A single four-way SUMO intersection with straight and turning movements."""
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET

from .config import ROOT, binary

DIRECTIONS = ("N", "S", "E", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}


def write_xml(path, root):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def network(config):
    sim = config["simulation"]
    signature = hashlib.sha256(json.dumps([sim["road_length_m"], sim["speed_limit_mps"], 1]).encode()).hexdigest()[:12]
    folder = ROOT / "data/generated" / f"course_junction_{signature}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "network.net.xml"
    if target.exists():
        return target
    nodes, edges, links = ET.Element("nodes"), ET.Element("edges"), ET.Element("connections")
    ET.SubElement(nodes, "node", id="J", x="0", y="0", type="traffic_light")
    for direction, (x, y) in zip(DIRECTIONS, [(0, 1), (0, -1), (1, 0), (-1, 0)]):
        ET.SubElement(nodes, "node", id=direction, x=str(x * sim["road_length_m"]), y=str(y * sim["road_length_m"]), type="priority")
        for suffix, start, end in [("in", direction, "J"), ("out", "J", direction)]:
            ET.SubElement(edges, "edge", {"id": f"{direction}_{suffix}", "from": start, "to": end, "numLanes": "1", "speed": str(sim["speed_limit_mps"])})
        for destination in DIRECTIONS:
            if direction != destination:
                ET.SubElement(links, "connection", {"from": f"{direction}_in", "to": f"{destination}_out", "fromLane": "0", "toLane": "0"})
    for name, content in [("nodes.xml", nodes), ("edges.xml", edges), ("links.xml", links)]:
        write_xml(folder / name, content)
    command = [binary("netconvert"), "--node-files", "nodes.xml", "--edge-files", "edges.xml", "--connection-files", "links.xml", "--output-file", target.name, "--no-turnarounds", "true", "--xml-validation", "never"]
    process_env = os.environ.copy()
    process_env.pop("SUMO_HOME", None)
    result = subprocess.run(command, cwd=folder, env=process_env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return target
