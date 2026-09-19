"""Focused integration checks for control constraints and evaluation accounting."""
from __future__ import annotations

import itertools
import unittest
import xml.etree.ElementTree as ET

from traffic_rl.runtime import ROOT, read_config
from traffic_rl.scenario import network, routes


class ProjectTests(unittest.TestCase):
    def test_network_phases_match_actual_connections(self):
        root = ET.parse(network(read_config())).getroot()
        links = {int(link.attrib["linkIndex"]): link.attrib["from"][0] for link in root.findall("connection") if link.get("tl") == "J"}
        states = [phase.attrib["state"] for phase in root.find("tlLogic").findall("phase")]
        greens = [{links[i] for i, color in enumerate(state) if color == "G"} for state in states if "G" in state]
        self.assertEqual(greens, [{"N", "S"}, {"E", "W"}])

    def test_demand_reproducible_and_held_out(self):
        config = read_config()
        one, count = routes(config, "balanced", 101)
        repeat, repeat_count = routes(config, "balanced", 101)
        other, _ = routes(config, "balanced", 102)
        self.assertEqual(one.read_bytes(), repeat.read_bytes())
        self.assertEqual(count, repeat_count)
        self.assertNotEqual(one.read_bytes(), other.read_bytes())
        first_train_seed = 100000 + config["training"]["seed"] * 1000
        self.assertGreater(first_train_seed, max(config["evaluation"]["seeds"]))

    def test_actual_signal_timing_and_gym_api(self):
        from stable_baselines3.common.env_checker import check_env
        from traffic_rl.environment import IntersectionEnv
        config = read_config()
        config["simulation"]["duration_seconds"] = 300
        env = IntersectionEnv(config, "peak", 101)
        try:
            check_env(env, warn=True)
            env.reset(seed=101)
            self.assertAlmostEqual(env.env.sumo.simulation.getDeltaT(), config["simulation"]["step_length"])
            original_step = env.env._sumo_step
            states = []
            collisions = []

            def observe_step():
                states.append(env.env.sumo.trafficlight.getRedYellowGreenState("J"))
                original_step()
                collisions.append(env.env.sumo.simulation.getCollidingVehiclesNumber())

            env.env._sumo_step = observe_step
            truncated = False
            while not truncated:
                # Always request the current phase: maximum-green guard must
                # force transitions without relying on a cooperative policy.
                _, _, terminated, truncated, _ = env.step(env.signal.green_phase)
                self.assertFalse(terminated)
                self.assertAlmostEqual(env.env.sim_step % config["simulation"]["delta_time"], 0)
            self.assertEqual(env.env.sim_step, config["simulation"]["duration_seconds"])
            self.assertGreater(env.forced_switches, 0)
            self.assertEqual(sum(collisions), 0)
            chunks = [(state, len(list(values))) for state, values in itertools.groupby(states)]
            for state, length in chunks[:-1]:  # Last run can be horizon-truncated.
                if "y" in state:
                    self.assertEqual(length, config["simulation"]["yellow_time"])
                else:
                    self.assertGreaterEqual(length, config["simulation"]["min_green"])
                    self.assertLessEqual(length, config["simulation"]["max_green"])
        finally:
            env.close()

    def test_metrics_include_unfinished_and_pending(self):
        from traffic_rl.metrics import episode_metrics
        folder = ROOT / "outputs/test_fixtures"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "routes.xml").write_text('<routes><vehicle id="N_0" depart="0"/><vehicle id="S_0" depart="1"/><vehicle id="E_0" depart="2"/></routes>', encoding="utf-8")
        (folder / "trips.xml").write_text('<tripinfos><tripinfo id="N_0" depart="0" arrival="8" waitingTime="3" departDelay="0"/><tripinfo id="S_0" depart="2" arrival="-1" waitingTime="4" departDelay="1"/></tripinfos>', encoding="utf-8")
        result = episode_metrics(folder / "trips.xml", folder / "routes.xml", 10, [])
        self.assertEqual(result["completed_vehicles"], 1)
        self.assertEqual(result["unfinished_vehicles"], 1)
        self.assertEqual(result["not_inserted_vehicles"], 1)
        self.assertAlmostEqual(result["mean_wait_plus_entry_delay_all_s"], 16 / 3)
        self.assertAlmostEqual(result["p95_stopped_wait_departed_s"], 3.95)


if __name__ == "__main__":
    unittest.main()
