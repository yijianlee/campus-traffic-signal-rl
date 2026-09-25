"""Exercise topology connectivity, signal clearance and shared policy spaces."""
import contextlib
import io
import itertools
import json
from argparse import Namespace
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from traffic_rl.runtime import read_config
from traffic_rl.roadnet import LAYOUTS, network, routes
from traffic_rl.multi_environment import RoadEnv


class DiversityTests(unittest.TestCase):
    def config(self, layout, seconds=600):
        c = read_config()
        c["layout"] = layout
        c["simulation"]["duration_seconds"] = seconds
        return c

    def test_routes_are_connected_and_reproducible(self):
        for layout in LAYOUTS:
            c = self.config(layout)
            net = ET.parse(network(c)).getroot()
            connections = {(l.get("from"), l.get("to")) for l in net.findall("connection")}
            path, count = routes(c, "surge", 101)
            original = path.read_bytes()
            same, _ = routes(c, "surge", 101)
            self.assertEqual(original, same.read_bytes())
            other, _ = routes(c, "surge", 102)
            self.assertNotEqual(original, other.read_bytes())
            self.assertGreater(count, 0)
            demand = ET.parse(path).getroot()
            self.assertEqual(len(demand.findall("route")), 6 if layout == "tjunction" else 12)
            for route in demand.findall("route"):
                edges = route.get("edges").split()
                self.assertTrue(all(pair in connections for pair in zip(edges, edges[1:])))
                if layout == "roundabout":
                    self.assertTrue(any(e.startswith("ring_") for e in edges))
            if layout == "roundabout":
                self.assertIsNotNone(net.find("roundabout"))

    def test_safety_and_maximum_green_for_all_layouts(self):
        for layout in LAYOUTS:
            env = RoadEnv(self.config(layout), "peak", 101)
            try:
                obs, _ = env.reset()
                self.assertEqual(obs.shape, (22,))
                self.assertEqual(env.action_space.n, 4)
                states = []
                original = env._sumo_step

                def record():
                    states.append(env.light_state())
                    original()

                env._sumo_step = record
                done = False
                while not done:
                    obs, _, _, done, info = env.step(env.phase)
                    self.assertTrue(env.observation_space.contains(obs))
                self.assertEqual(info["collisions"], 0)
                self.assertEqual(info["teleports"], 0)
                self.assertGreater(env.forced_switches, 0)
                self.assertGreater(env.sumo.simulation.getArrivedNumber() + sum(env.sumo.edge.getLastStepVehicleNumber(f"{d}_out") for d in env.active), 0)
                for state, group in itertools.groupby(states):
                    self.assertLessEqual(state.lower().count("g"), 1)
                chunks = [(s, len(list(g))) for s, g in itertools.groupby(states)]
                for state, length in chunks[:-1]:
                    if "y" in state:
                        self.assertEqual(length, 3)
                    elif "G" in state:
                        self.assertGreaterEqual(length, 10)
                        self.assertLessEqual(length, 60)
                    else:
                        self.assertEqual(length, 2)
            finally:
                env.close()

    def test_mixed_spaces_and_episode_selection(self):
        from stable_baselines3.common.env_checker import check_env
        env = RoadEnv(self.config("mixed", 20), "mixed", 42, vary_demand=True)
        try:
            check_env(env, warn=True)
            env.reset(seed=42)
            selections = []
            for _ in range(18):
                obs, _ = env.reset()
                selections.append((env.layout, env.scenario))
                self.assertTrue(env.observation_space.contains(obs))
            self.assertEqual({v[0] for v in selections}, set(LAYOUTS))
            self.assertEqual({v[1] for v in selections}, {"balanced", "peak", "tidal", "surge"})
            env.reset(seed=42)
            repeated = []
            for _ in range(18):
                env.reset()
                repeated.append((env.layout, env.scenario))
            self.assertEqual(selections, repeated)
        finally:
            env.close()

    def test_roundabout_replay_and_unmetered_baseline(self):
        from traffic_rl.presentation import present
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            present(Namespace(model=None, out=None, seed=101, scenarios=["surge"], no_open=True), self.config("roundabout", 120))
        page = Path(output.getvalue().split("Presentation ready: ")[-1].strip())
        data = json.loads((page.parent / "recordings.js").read_text(encoding="utf-8").removeprefix("window.TRAFFIC_REPLAY=").removesuffix(";"))
        self.assertEqual(len(data["geometry"]["signals"]), 4)
        self.assertTrue(any(l["id"].startswith("ring_") for l in data["geometry"]["lanes"]))
        self.assertEqual(len({r["demandHash"] for r in data["runs"]}), 1)
        for run in data["runs"]:
            self.assertEqual(run["metrics"]["collision_vehicle_events"], 0)
            self.assertEqual(run["metrics"]["teleport_events"], 0)
            self.assertEqual(run["frames"][-1]["completed"], run["metrics"]["completed_vehicles"])
            if run["policy"] == "yield":
                self.assertTrue(all(f["light"] == "GGGG" for f in run["frames"]))
                self.assertEqual(run["metrics"]["switches"], 0)
