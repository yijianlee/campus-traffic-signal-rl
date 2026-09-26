"""Refactoring must preserve the recorded dynamics and portable package contents."""
import json
from pathlib import Path
from traffic_rl.common.artifacts import output_dir
import unittest

from traffic_rl.common.runtime import ROOT, read_config
from traffic_rl.envs.factory import make_env
from traffic_rl.replay.package import read_package, write_package


class RefactorTests(unittest.TestCase):
    def test_preserved_behavior(self):
        expected = json.loads((Path(__file__).parent / "fixtures/behavior.json").read_text())
        for layout, steps in expected.items():
            config = read_config()
            config["layout"] = layout
            config["simulation"]["duration_seconds"] = 60
            env = make_env(config, "peak", 101)
            try:
                env.reset(seed=101)
                for before in steps:
                    action = env.baseline_action("queue")
                    obs, reward, _, _, info = env.step(action)
                    actual = {"observation": obs.tolist(), "action": action, "reward": reward,
                              "phase": info["phase"], "queues": list(env.queues().values())}
                    self.assertEqual(actual, before, layout)
            finally:
                env.close()

    def test_lazy_package_roundtrip(self):
        data = {"version": 2, "layouts": [], "runs": [
            {"layout": "roundabout", "policy": "yield", "frames": [{"t": 0}],
             "decisions": [], "vehicleIds": ["N_1"]}]}
        folder = output_dir(None, "package_test")
        write_package(data, folder)
        catalog = json.loads((Path(folder) / "recordings.js").read_text().split("=", 1)[1][:-1])
        self.assertNotIn("frames", catalog["runs"][0])
        self.assertNotIn("decisions", catalog["runs"][0])
        self.assertEqual(read_package(folder)["runs"], data["runs"])
        self.assertTrue((Path(folder) / "scripts/loader.js").is_file())
