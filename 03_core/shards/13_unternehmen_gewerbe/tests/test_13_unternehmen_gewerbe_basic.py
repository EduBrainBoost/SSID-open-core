"""Basic tests for Core / Unternehmen & Gewerbe shard."""
import os
import unittest

import yaml


SHARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PATH = os.path.join(SHARD_DIR, "chart.yaml")


class TestValidator13UnternehmenGewerbeBasic(unittest.TestCase):
    """Validate chart.yaml integrity for 13_unternehmen_gewerbe."""

    @classmethod
    def setUpClass(cls):
        with open(CHART_PATH, "r", encoding="utf-8") as fh:
            cls.chart = yaml.safe_load(fh)

    def test_capabilities_not_empty(self):
        caps = self.chart.get("capabilities", {})
        must = caps.get("must", [])
        self.assertTrue(len(must) > 0, "capabilities.must must not be empty")

    def test_policies_hash_only(self):
        policies = self.chart.get("policies", [])
        ids = [p.get("id") for p in policies]
        self.assertIn("hash_only", ids, "hash_only policy required")

    def test_policies_non_custodial(self):
        policies = self.chart.get("policies", [])
        ids = [p.get("id") for p in policies]
        self.assertIn("non_custodial", ids, "non_custodial policy required")

    def test_version_present(self):
        self.assertIn("version", self.chart, "version field required")
        self.assertTrue(len(self.chart["version"]) > 0)

    def test_shard_name_correct(self):
        self.assertEqual(self.chart.get("shard"), "13_unternehmen_gewerbe")


if __name__ == "__main__":
    unittest.main()
