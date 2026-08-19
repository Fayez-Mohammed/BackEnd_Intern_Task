"""
Unit tests for database adapter instantiation and contract conformance.
"""

import unittest
from benchmark.adapters import ADAPTER_MAP, BaseGraphAdapter


class TestAdapters(unittest.TestCase):
    def test_all_adapters_registered(self):
        expected = {"cognodb", "neo4j", "memgraph", "falkordb", "arangodb", "kuzu"}
        self.assertTrue(expected.issubset(set(ADAPTER_MAP.keys())))

    def test_adapter_inheritance(self):
        for name, cls in ADAPTER_MAP.items():
            self.assertTrue(
                issubclass(cls, BaseGraphAdapter),
                f"Adapter {name} must inherit from BaseGraphAdapter"
            )

    def test_kuzu_adapter_lifecycle(self):
        kuzu_cls = ADAPTER_MAP["kuzu"]
        adapter = kuzu_cls("kuzu", {}, {"database_path": "data/test_kuzu_db"})
        connected = adapter.connect()
        self.assertTrue(connected)
        health = adapter.health_check()
        self.assertEqual(health.get("status"), "healthy")
        adapter.close()


if __name__ == "__main__":
    unittest.main()
