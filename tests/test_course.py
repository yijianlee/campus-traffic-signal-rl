"""Course invariants: reproducible traffic, valid control and truthful replay."""
from argparse import Namespace
import unittest
import xml.etree.ElementTree as ET

from traffic_rl.config import read_config
from traffic_rl.demand import profile, routes
from traffic_rl.env import IntersectionEnv
from traffic_rl.network import network


class CourseTests(unittest.TestCase):
    def config(self, seconds=120):
        config = read_config()
        config["simulation"]["duration_seconds"] = seconds
        return config

    def test_composite_reproducibility_and_connectivity(self):
        config = self.config(600)
        path, count = routes(config, 101)
        first = path.read_bytes()
        self.assertEqual(routes(config, 101)[0].read_bytes(), first)
        self.assertNotEqual(routes(config, 102)[0].read_bytes(), first)
        segments = profile(config, 101)
        self.assertEqual(segments[0]["start"], 0)
        self.assertEqual(segments[-1]["end"], 600)
        self.assertGreater(segments[2]["rates"]["N"], segments[2]["rates"]["E"])
        self.assertGreater(segments[8]["rates"]["E"], segments[8]["rates"]["N"])
        root = ET.parse(path).getroot()
        self.assertEqual(len(root.findall("vehicle")), count)
        self.assertEqual(len(root.findall("route")), 12)
        net = ET.parse(network(config)).getroot()
        connections = {(c.get("from"), c.get("to")) for c in net.findall("connection")}
        self.assertTrue(all(tuple(r.get("edges").split()) in connections for r in root.findall("route")))

    def test_gym_interface_and_seed_partition(self):
        from stable_baselines3.common.env_checker import check_env
        env = IntersectionEnv(self.config(), 42, vary_demand=True)
        try:
            check_env(env, warn=True)
            env.reset(seed=42)
            first = env.episodes[-1]["demand_seed"]
            env.reset()
            self.assertEqual(env.episodes[-1]["demand_seed"], first + 1)
            self.assertGreaterEqual(first, 100000)
            env.reset(seed=42)
            self.assertEqual(env.episodes[-1]["demand_seed"], first)
            self.assertEqual(env.observation_space.shape, (14,))
            with self.assertRaises(ValueError):
                env.step(4)
        finally:
            env.close()

    def test_signal_constraints_and_reward(self):
        env = IntersectionEnv(self.config(300), 101)
        try:
            env.reset()
            samples, lights = [], []
            original = env._sumo_step
            def observe():
                lights.append(env.light_state())
                original()
                samples.append(sum(env.sumo.vehicle.getSpeed(v) < .1 for v in env.sumo.vehicle.getIDList()))
            env._sumo_step = observe
            _, _, _, _, info = env.step(1)
            self.assertEqual(info["action_reason"], "min_green")
            env.step(0)
            _, reward, _, _, info = env.step(1)
            self.assertEqual(info["action_reason"], "switch")
            self.assertEqual(lights[-5:], ["yrrr"] * 3 + ["rrrr"] * 2)
            self.assertAlmostEqual(reward, -sum(samples[-5:]) / 5 - .2)
            self.assertAlmostEqual(reward, sum(info["reward_terms"].values()))
            done = False
            while not done:
                _, _, _, done, info = env.step(env.phase)
            self.assertGreater(env.forced_switches, 0)
            self.assertEqual(env.collisions, 0)
            self.assertEqual(env.teleports, 0)
            self.assertTrue(all(sum(c.lower() == 'g' for c in light) <= 1 for light in lights))
        finally:
            env.close()

    def test_replay_roundtrip(self):
        from stable_baselines3 import DQN
        from traffic_rl.artifacts import output_dir
        from traffic_rl.replay import present
        from traffic_rl.package import read_package
        folder = output_dir(None, "replay_test")
        config = self.config(20)
        env = IntersectionEnv(config, 101)
        model = DQN("MlpPolicy", env, seed=42, device="cpu")
        model.save(folder / "model")
        env.close()
        data, result = present(Namespace(model=str(folder / "model.zip"), out=None, seed=101, no_open=True), config)
        run = read_package(result)["runs"][0]
        self.assertEqual(len(data["runs"]), 1)
        self.assertEqual(run["policy"], "dqn")
        self.assertEqual(len(run["decisions"]), 4)
        self.assertEqual(len(run["frames"]), 101)
        self.assertEqual(len(run["observationLabels"]), 14)
        self.assertEqual(run["frames"][-1]["completed"], run["metrics"]["completed_vehicles"])
        for i, decision in enumerate(run["decisions"]):
            self.assertAlmostEqual(decision["reward"], sum(decision["rewardTerms"].values()))
            if i:
                self.assertEqual(run["decisions"][i-1]["nextObservation"], decision["observation"])
