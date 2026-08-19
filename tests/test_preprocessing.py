"""
Unit tests for dataset preprocessing and manifest verification.
"""

import json
import unittest
from pathlib import Path
import pandas as pd


class TestPreprocessing(unittest.TestCase):
    def test_processed_files_exist(self):
        nodes_path = Path("data/processed/nodes.csv")
        edges_path = Path("data/processed/edges.csv")
        manifest_path = Path("data/processed/manifest.json")

        self.assertTrue(nodes_path.exists(), "nodes.csv must exist")
        self.assertTrue(edges_path.exists(), "edges.csv must exist")
        self.assertTrue(manifest_path.exists(), "manifest.json must exist")

    def test_dataset_integrity(self):
        df_nodes = pd.read_csv("data/processed/nodes.csv")
        df_edges = pd.read_csv("data/processed/edges.csv")

        self.assertEqual(len(df_nodes), 37700, "Must contain exactly 37,700 nodes")
        self.assertEqual(len(df_edges), 289003, "Must contain exactly 289,003 edges")

        # Verify columns
        self.assertListEqual(list(df_nodes.columns), ["node_id", "username", "developer_type"])
        self.assertListEqual(list(df_edges.columns), ["source_id", "target_id", "rel_type"])

        # Verify no nulls
        self.assertEqual(df_nodes["node_id"].isnull().sum(), 0)
        self.assertEqual(df_edges["source_id"].isnull().sum(), 0)


if __name__ == "__main__":
    unittest.main()
