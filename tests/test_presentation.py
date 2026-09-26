from traffic_rl.replay.package import read_package
"""Verify a real portable replay export, including metrics and shared demand."""
import contextlib
import io
import json
from argparse import Namespace
from pathlib import Path
import unittest

from traffic_rl.presentation import present
from traffic_rl.runtime import read_config


class PresentationTests(unittest.TestCase):
    def test_recorded_export(self):
        config = read_config()
        config["simulation"]["duration_seconds"] = 20
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            present(Namespace(model=None, out=None, seed=101, scenarios=["balanced"], no_open=True), config)
        page = Path(output.getvalue().split("Presentation ready: ")[-1].strip())
        data = read_package(page.parent)
        self.assertEqual(len(data["runs"]), 2)
        self.assertEqual(data["runs"][0]["demandHash"], data["runs"][1]["demandHash"])
        self.assertIsNone(data["modelNote"])
        for run in data["runs"]:
            self.assertEqual(len(run["frames"]), 101)
            self.assertEqual(run["frames"][0]["t"], 0)
            self.assertEqual(run["frames"][-1]["t"], 20)
            self.assertEqual(run["frames"][-1]["completed"], run["metrics"]["completed_vehicles"])
            self.assertEqual(len(run["frames"][-1]["v"]), run["metrics"]["unfinished_vehicles"])
            for frame in run["frames"]:
                self.assertEqual(len(frame["q"]), 4)
                self.assertFalse(frame["light"][0].lower() == "g" and frame["light"][2].lower() == "g")
                self.assertEqual(len({v[0] for v in frame["v"]}), len(frame["v"]))
        for name in ("index.html", "styles/app.css", "scripts/app.js", "recordings.js", "manifest.json"):
            self.assertTrue((page.parent / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
