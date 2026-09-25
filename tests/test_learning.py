"""Learning records must describe actual transitions and controller overrides."""
import contextlib
import io
from argparse import Namespace
import unittest

from traffic_rl.runtime import read_config
from traffic_rl.presentation import present
from traffic_rl.multi_environment import RoadEnv


class LearningTests(unittest.TestCase):
    def test_bundle_and_transition_accounting(self):
        config = read_config()
        config["simulation"]["duration_seconds"] = 40
        args = Namespace(layouts=["intersection", "tjunction", "roundabout"], model=None, out=None, seed=101, scenarios=["balanced", "surge"], no_open=True)
        with contextlib.redirect_stdout(io.StringIO()):
            data, folder = present(args, config)
        self.assertEqual({s["id"] for s in data["layouts"]}, {"intersection", "tjunction", "roundabout"})
        self.assertEqual(len(data["runs"]), 12)
        self.assertTrue((folder / "renderer.js").exists())
        for run in data["runs"]:
            decisions = run["decisions"]
            self.assertEqual(len(decisions), 8)
            self.assertEqual(decisions[0]["start"], 0)
            self.assertEqual(decisions[-1]["end"], 40)
            shape = 13 if run["layout"] == "intersection" else 22
            self.assertEqual(len(run["observationLabels"]), shape)
            for i, d in enumerate(decisions):
                self.assertEqual(d["end"] - d["start"], 5)
                self.assertEqual(len(d["observation"]), shape)
                self.assertAlmostEqual(d["reward"], sum(d["rewardTerms"].values()))
                weights = data["rewardWeights"]
                self.assertAlmostEqual(d["rewardTerms"]["stopped"], -d["rewardInputs"]["stopped"] * weights["queue_weight"])
                self.assertAlmostEqual(d["rewardTerms"]["switch"], -d["rewardInputs"]["switch"] * weights["switch_weight"])
                if i:
                    self.assertEqual(decisions[i-1]["nextObservation"], d["observation"])
                    self.assertEqual(decisions[i-1]["nextState"], d["state"])
                if run["policy"] == "yield":
                    self.assertEqual(d["reason"], "unmetered")
                if run["layout"] == "tjunction":
                    self.assertIsNone(d["state"]["density"]["N"])

    def test_override_reasons_and_reward_inputs(self):
        config = read_config()
        config["layout"] = "tjunction"
        config["reward"]["queue_weight"] = 1.7
        config["reward"]["switch_weight"] = 2.5
        env = RoadEnv(config, "peak", 101)
        try:
            env.reset()
            _, reward, _, _, info = env.step(2)
            self.assertEqual(info["action_reason"], "min_green")
            self.assertEqual(info["phase"], 1)
            _, reward, _, _, info = env.step(0)
            self.assertEqual(info["action_reason"], "invalid")
            self.assertEqual(info["reward_terms"]["invalid"], -1)
            _, reward, _, _, info = env.step(2)
            self.assertEqual(info["action_reason"], "switch")
            self.assertEqual(info["reward_terms"]["switch"], -2.5)
            self.assertAlmostEqual(reward, sum(info["reward_terms"].values()))
            while info["action_reason"] != "max_green":
                _, reward, _, _, info = env.step(env.phase)
            self.assertEqual(info["forced_switch"], 1)
            self.assertAlmostEqual(reward, sum(info["reward_terms"].values()))
        finally:
            env.close()
