#!/usr/bin/env python3
"""
Deterministic Dataset Preprocessing Pipeline
Converts raw SNAP musae-github files into standardized CSVs for all database adapters.
Generates SHA256 checksums and verification manifest.
"""

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_TARGET = RAW_DIR / "musae_git_target.csv"
RAW_EDGES = RAW_DIR / "musae_git_edges.csv"

OUT_NODES = PROCESSED_DIR / "nodes.csv"
OUT_EDGES = PROCESSED_DIR / "edges.csv"
OUT_MANIFEST = PROCESSED_DIR / "manifest.json"

EXPECTED_NODES = 37700
EXPECTED_EDGES = 289003


def calculate_sha256(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def preprocess() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_TARGET.exists() or not RAW_EDGES.exists():
        logger.error(f"Raw data files missing in {RAW_DIR}. Run scripts/download_dataset.py first.")
        return 1

    logger.info("Reading raw target file (nodes)...")
    df_nodes = pd.read_csv(RAW_TARGET)
    logger.info(f"Raw nodes columns: {list(df_nodes.columns)}, row count: {len(df_nodes)}")

    # Standardize node columns: node_id (int), username (str), developer_type (str)
    # Raw target has columns: id, name, ml_target
    df_nodes = df_nodes.rename(columns={"id": "node_id", "name": "username"})
    df_nodes["node_id"] = df_nodes["node_id"].astype(int)
    df_nodes["username"] = df_nodes["username"].astype(str)
    df_nodes["developer_type"] = df_nodes["ml_target"].apply(lambda x: "ml" if int(x) == 1 else "web")
    
    # Sort deterministically by node_id
    df_nodes = df_nodes.sort_values(by="node_id").reset_index(drop=True)
    df_nodes = df_nodes[["node_id", "username", "developer_type"]]

    logger.info(f"Saving standardized nodes to {OUT_NODES}...")
    df_nodes.to_csv(OUT_NODES, index=False)

    logger.info("Reading raw edges file...")
    df_edges = pd.read_csv(RAW_EDGES)
    logger.info(f"Raw edges columns: {list(df_edges.columns)}, row count: {len(df_edges)}")

    # Standardize edge columns: source_id (int), target_id (int), rel_type (str)
    # Raw edges has columns: id_1, id_2
    df_edges = df_edges.rename(columns={"id_1": "source_id", "id_2": "target_id"})
    df_edges["source_id"] = df_edges["source_id"].astype(int)
    df_edges["target_id"] = df_edges["target_id"].astype(int)
    df_edges["rel_type"] = "MUTUAL_FOLLOW"

    # Sort deterministically by source_id, target_id
    df_edges = df_edges.sort_values(by=["source_id", "target_id"]).reset_index(drop=True)
    df_edges = df_edges[["source_id", "target_id", "rel_type"]]

    logger.info(f"Saving standardized edges to {OUT_EDGES}...")
    df_edges.to_csv(OUT_EDGES, index=False)

    # Verification
    nodes_count = len(df_nodes)
    edges_count = len(df_edges)
    nodes_sha256 = calculate_sha256(OUT_NODES)
    edges_sha256 = calculate_sha256(OUT_EDGES)

    logger.info(f"Validation summary: Nodes={nodes_count} (Expected={EXPECTED_NODES}), Edges={edges_count} (Expected={EXPECTED_EDGES})")

    if nodes_count != EXPECTED_NODES:
        logger.warning(f"Node count mismatch: {nodes_count} != {EXPECTED_NODES}")
    if edges_count != EXPECTED_EDGES:
        logger.warning(f"Edge count mismatch: {edges_count} != {EXPECTED_EDGES}")

    manifest = {
        "dataset_name": "SNAP musae-github (GitHub Social Network)",
        "source": "Stanford Large Network Dataset Collection",
        "processed_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": {
            "file": str(OUT_NODES.as_posix()),
            "count": nodes_count,
            "sha256": nodes_sha256,
            "schema": {
                "node_id": "int (primary key)",
                "username": "string (GitHub handle)",
                "developer_type": "string ('ml' or 'web')"
            },
            "class_distribution": df_nodes["developer_type"].value_counts().to_dict()
        },
        "edges": {
            "file": str(OUT_EDGES.as_posix()),
            "count": edges_count,
            "sha256": edges_sha256,
            "schema": {
                "source_id": "int",
                "target_id": "int",
                "rel_type": "string ('MUTUAL_FOLLOW')"
            }
        }
    }

    with open(OUT_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Manifest written to {OUT_MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(preprocess())
