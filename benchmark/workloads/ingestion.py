"""
Data Ingestion Workload Runner
Measures node and relationship loading throughput (items/sec) and total wall-clock time.
"""

import logging
import time
from typing import Any, Dict
import pandas as pd

from ..adapters.base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


def run_ingestion_workload(
    adapter: BaseGraphAdapter,
    df_nodes: pd.DataFrame,
    df_edges: pd.DataFrame,
    batch_size: int = 1000
) -> Dict[str, Any]:
    logger.info(f"[{adapter.name}] Starting fresh data ingestion benchmark...")
    
    # 1. Clear database
    adapter.clear_database()

    # 2. Ingest Nodes
    logger.info(f"[{adapter.name}] Ingesting {len(df_nodes)} nodes (batch_size={batch_size})...")
    with HighResolutionTimer() as node_timer:
        nodes_loaded, _ = adapter.load_nodes(df_nodes, batch_size=batch_size)
    node_sec = node_timer.elapsed_sec
    nodes_per_sec = (nodes_loaded / node_sec) if node_sec > 0 else 0.0

    # 3. Create Indexes after nodes load
    logger.info(f"[{adapter.name}] Creating indexes...")
    with HighResolutionTimer() as index_timer:
        adapter.create_indexes()
    index_sec = index_timer.elapsed_sec

    # 4. Ingest Edges
    logger.info(f"[{adapter.name}] Ingesting {len(df_edges)} edges (batch_size={batch_size})...")
    with HighResolutionTimer() as edge_timer:
        edges_loaded, _ = adapter.load_edges(df_edges, batch_size=batch_size)
    edge_sec = edge_timer.elapsed_sec
    edges_per_sec = (edges_loaded / edge_sec) if edge_sec > 0 else 0.0

    total_load_sec = node_sec + edge_sec + index_sec

    logger.info(
        f"[{adapter.name}] Ingestion complete: "
        f"Nodes={nodes_loaded} ({nodes_per_sec:.1f}/s), "
        f"Edges={edges_loaded} ({edges_per_sec:.1f}/s), "
        f"Total Time={total_load_sec:.2f}s"
    )

    return {
        "nodes_loaded": nodes_loaded,
        "edges_loaded": edges_loaded,
        "node_load_time_sec": round(node_sec, 4),
        "edge_load_time_sec": round(edge_sec, 4),
        "index_creation_time_sec": round(index_sec, 4),
        "total_wall_clock_sec": round(total_load_sec, 4),
        "nodes_per_sec": round(nodes_per_sec, 2),
        "edges_per_sec": round(edges_per_sec, 2),
        "batch_size": batch_size
    }
