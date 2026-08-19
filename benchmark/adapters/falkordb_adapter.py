"""
FalkorDB Database Adapter (FalkorDB Cloud and FalkorDB Community)
Connects to FalkorDB via official falkordb driver using Cypher over RESP protocol.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from falkordb import FalkorDB

from .base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


class FalkorDBAdapter(BaseGraphAdapter):
    def __init__(self, name: str, config: Dict[str, Any], env_vars: Dict[str, str]):
        super().__init__(name, config, env_vars)
        self.host = env_vars.get("host", "localhost")
        self.port = int(env_vars.get("port", 6379))
        self.password = env_vars.get("password", None) or None
        self.graph_name = env_vars.get("graph_name", "github_benchmark")
        self.client: Optional[FalkorDB] = None
        self.graph = None

    def connect(self) -> bool:
        try:
            self.client = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password,
                socket_timeout=30.0
            )
            self.graph = self.client.select_graph(self.graph_name)
            # Verify connectivity
            self.client.connection.ping()
            self.is_connected = True
            logger.info(f"[{self.name}] Successfully connected to {self.host}:{self.port}, graph='{self.graph_name}'")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            self.is_connected = False
            return False

    def close(self) -> None:
        if self.client:
            try:
                self.client.connection.close()
            except Exception:
                pass
            self.is_connected = False
            logger.info(f"[{self.name}] Connection closed.")

    def health_check(self) -> Dict[str, Any]:
        if not self.is_connected or not self.client:
            return {"status": "unhealthy", "error": "Not connected"}
        try:
            with HighResolutionTimer() as timer:
                val = self.client.connection.ping()
            return {
                "status": "healthy",
                "ping_rtt_ms": round(timer.elapsed_ms, 2),
                "response": val
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def clear_database(self) -> bool:
        if not self.graph:
            return False
        try:
            logger.info(f"[{self.name}] Clearing graph '{self.graph_name}'...")
            try:
                self.graph.delete()
            except Exception:
                pass
            # Re-select fresh graph
            self.graph = self.client.select_graph(self.graph_name)
            logger.info(f"[{self.name}] Graph cleared successfully.")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to clear graph: {e}")
            return False

    def create_indexes(self) -> None:
        if not self.graph:
            return
        logger.info(f"[{self.name}] Creating indexes on Developer(node_id) and Developer(developer_type)...")
        try:
            self.graph.query("CREATE INDEX FOR (d:Developer) ON (d.node_id)")
        except Exception as e:
            logger.warning(f"[{self.name}] Index on node_id notice: {e}")
        try:
            self.graph.query("CREATE INDEX FOR (d:Developer) ON (d.developer_type)")
        except Exception as e:
            logger.warning(f"[{self.name}] Index on developer_type notice: {e}")

    def load_nodes(self, df_nodes: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.graph:
            return 0, 0.0
        total_loaded = 0
        records = df_nodes.to_dict(orient="records")
        start_time = time.perf_counter()

        query = """
        UNWIND $batch AS row
        CREATE (d:Developer {
            node_id: toInteger(row.node_id),
            username: toString(row.username),
            developer_type: toString(row.developer_type)
        })
        """

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.graph.query(query, {"batch": batch})
            total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def load_edges(self, df_edges: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.graph:
            return 0, 0.0
        total_loaded = 0
        records = df_edges.to_dict(orient="records")
        start_time = time.perf_counter()

        query = """
        UNWIND $batch AS row
        MATCH (src:Developer {node_id: toInteger(row.source_id)})
        MATCH (tgt:Developer {node_id: toInteger(row.target_id)})
        CREATE (src)-[:MUTUAL_FOLLOW]->(tgt)
        """

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.graph.query(query, {"batch": batch})
            total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def warmup(self, sample_node_ids: List[int], iterations: int = 30) -> None:
        if not self.graph:
            return
        logger.info(f"[{self.name}] Executing {iterations} warmup queries...")
        for node_id in sample_node_ids[:iterations]:
            try:
                self.graph.query(
                    "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW]-(m:Developer) RETURN count(DISTINCT m)",
                    {"id": int(node_id)}
                )
            except Exception:
                pass

    def traversal_1hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        res = self.graph.query(query, {"id": int(start_node_id)})
        if res.result_set:
            return res.result_set[0][0]
        return 0

    def traversal_2hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*2]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        res = self.graph.query(query, {"id": int(start_node_id)})
        if res.result_set:
            return res.result_set[0][0]
        return 0

    def traversal_3hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*3]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        res = self.graph.query(query, {"id": int(start_node_id)})
        if res.result_set:
            return res.result_set[0][0]
        return 0

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        query = "MATCH (n:Developer {node_id: $id}) RETURN n.node_id AS id, n.username AS username, n.developer_type AS developer_type"
        res = self.graph.query(query, {"id": int(node_id)})
        if res.result_set:
            row = res.result_set[0]
            return {"id": row[0], "username": row[1], "developer_type": row[2]}
        return None

    def indexed_lookup(self, developer_type: str) -> int:
        query = "MATCH (n:Developer {developer_type: $dev_type}) RETURN count(n) AS cnt"
        res = self.graph.query(query, {"dev_type": str(developer_type)})
        if res.result_set:
            return res.result_set[0][0]
        return 0

    def aggregation(self) -> List[Dict[str, Any]]:
        query = "MATCH (n:Developer) RETURN n.developer_type AS dev_type, count(n) AS total ORDER BY total DESC"
        res = self.graph.query(query)
        output = []
        for row in res.result_set:
            output.append({"dev_type": row[0], "total": row[1]})
        return output

    def write_edge(self, source_id: int, target_id: int) -> bool:
        query = """
        MATCH (a:Developer {node_id: $src}), (b:Developer {node_id: $dst})
        CREATE (a)-[r:BENCH_TEMP]->(b)
        RETURN count(r) AS cnt
        """
        try:
            self.graph.query(query, {"src": int(source_id), "dst": int(target_id)})
            return True
        except Exception:
            return False

    def get_footprint(self) -> Dict[str, Any]:
        try:
            info = self.client.connection.info("memory")
            return {
                "engine": "GraphBLAS Sparse Adjacency Matrix",
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "used_memory_peak_human": info.get("used_memory_peak_human", "N/A")
            }
        except Exception:
            return {
                "engine": "GraphBLAS Sparse Adjacency Matrix",
                "stored_data_size": "Sparse CSR/CSC Matrix RAM representation",
                "memory_usage": "Free Tier Limit: 100 MB"
            }
