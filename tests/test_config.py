"""
Unit tests for configuration loader and environment resolver.
"""

import os
import unittest
from pathlib import Path
from benchmark.config import BenchmarkConfig


class TestBenchmarkConfig(unittest.TestCase):
    def setUp(self):
        self.config = BenchmarkConfig("config/benchmark.yaml")

    def test_load_config_valid(self):
        self.assertEqual(self.config.random_seed, 42)
        self.assertIn("ingestion", self.config.workloads_config)
        self.assertIn("traversals", self.config.workloads_config)

    def test_database_keys_present(self):
        db_keys = self.config.databases_config.keys()
        self.assertIn("cognodb", db_keys)
        self.assertIn("neo4j", db_keys)
        self.assertIn("memgraph", db_keys)
        self.assertIn("falkordb", db_keys)
        self.assertIn("arangodb", db_keys)
        self.assertIn("kuzu", db_keys)

    def test_env_resolution(self):
        os.environ["COGNODB_URI"] = "bolt+s://test.cognodb.com:7687"
        os.environ["COGNODB_USER"] = "testuser"
        env = self.config.get_database_env("cognodb")
        self.assertEqual(env.get("uri"), "bolt+s://test.cognodb.com:7687")
        self.assertEqual(env.get("user"), "testuser")


if __name__ == "__main__":
    unittest.main()
