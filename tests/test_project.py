import unittest
from traffic_rl.config import ROOT

class MetricsTests(unittest.TestCase):
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
