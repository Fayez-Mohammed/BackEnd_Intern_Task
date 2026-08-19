"""
ArangoDB Database Adapter (ArangoGraph Cloud and ArangoDB Community)
Connects to ArangoDB via python-arango using AQL (ArangoDB Query Language).
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from arango import ArangoClient
from arango.database import StandardDatabase

from .base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


class ArangoDBAdapter(BaseGraphAdapter):
    def __init__(self, name: str, config: Dict[str, Any], env_vars: Dict[str, str]):
        super().__init__(name, config, env_vars)
        self.url = env_vars.get("url", "http://localhost:8529")
        self.user = env_vars.get("user", "root")
        self.password = env_vars.get("password", "")
        self.db_name = env_vars.get("database", "github_benchmark")
        self.client: Optional[ArangoClient] = None
        self.db: Optional[StandardDatabase] = None

    def connect(self) -> bool:
        try:
            self.client = ArangoClient(hosts=self.url, request_timeout=30)
            sys_db = self.client.db("_system", username=self.user, password=self.password)
            if not sys_db.has_database(self.db_name):
                sys_db.create_database(self.db_name)
            self.db = self.client.db(self.db_name, username=self.user, password=self.password)
            # Verify connectivity
            self.db.version()
            self.is_connected = True
            logger.info(f"[{self.name}] Successfully connected to {self.url}, database='{self.db_name}'")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            self.is_connected = False
            return False

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info(f"[{self.name}] Client closed.")

    def health_check(self) -> Dict[str, Any]:
        if not self.is_connected or not self.db:
            return {"status": "unhealthy", "error": "Not connected"}
        try:
            with HighResolutionTimer() as timer:
                res = self.db.aql.execute("RETURN 1").next()
            return {
                "status": "healthy",
                "ping_rtt_ms": round(timer.elapsed_ms, 2),
                "response": res
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def clear_database(self) -> bool:
        if not self.db:
            return False
        try:
            logger.info(f"[{self.name}] Clearing collections in '{self.db_name}'...")
            if self.db.has_graph("github_graph"):
                self.db.delete_graph("github_graph", drop_collections=True)
            for col in ["Developer", "MutualFollow", "BenchTemp"]:
                if self.db.has_collection(col):
                    self.db.delete_collection(col)
            
            # Recreate collections and graph
            dev_col = self.db.create_collection("Developer")
            mf_col = self.db.create_collection("MutualFollow", edge=True)
            self.db.create_collection("BenchTemp", edge=True)
            
            if not self.db.has_graph("github_graph"):
                self.db.create_graph(
                    "github_graph",
                    edge_definitions=[
                        {
                            "edge_collection": "MutualFollow",
                            "from_vertex_collections": ["Developer"],
                            "to_vertex_collections": ["Developer"]
                        }
                    ]
                )
            logger.info(f"[{self.name}] Database cleared and graph structure initialized.")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to clear database: {e}")
            return False

    def create_indexes(self) -> None:
        if not self.db:
            return
        logger.info(f"[{self.name}] Creating indexes on Developer(node_id) and Developer(developer_type)...")
        try:
            dev_col = self.db.collection("Developer")
            dev_col.add_persistent_index(fields=["node_id"], unique=False)
            dev_col.add_persistent_index(fields=["developer_type"], unique=False)
        except Exception as e:
            logger.warning(f"[{self.name}] Index creation notice: {e}")

    def load_nodes(self, df_nodes: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.db:
            return 0, 0.0
        total_loaded = 0
        records = df_nodes.to_dict(orient="records")
        start_time = time.perf_counter()
        dev_col = self.db.collection("Developer")

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            docs = []
            for r in batch:
                docs.append({
                    "_key": str(r["node_id"]),
                    "node_id": int(r["node_id"]),
                    "username": str(r["username"]),
                    "developer_type": str(r["developer_type"])
                })
            dev_col.insert_many(docs, silent=True)
            total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def load_edges(self, df_edges: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.db:
            return 0, 0.0
        total_loaded = 0
        records = df_edges.to_dict(orient="records")
        start_time = time.perf_counter()
        mf_col = self.db.collection("MutualFollow")

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            edges = []
            for r in batch:
                edges.append({
                    "_from": f"Developer/{r['source_id']}",
                    "_to": f"Developer/{r['target_id']}",
                    "rel_type": "MUTUAL_FOLLOW"
                })
            mf_col.insert_many(edges, silent=True)
            total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def warmup(self, sample_node_ids: List[int], iterations: int = 30) -> None:
        if not self.db:
            return
        logger.info(f"[{self.name}] Executing {iterations} warmup queries...")
        for node_id in sample_node_ids[:iterations]:
            try:
                aql = "FOR v IN 1..1 ANY CONCAT('Developer/', @id) GRAPH 'github_graph' RETURN DISTINCT v._key"
                cursor = self.db.aql.execute(aql, bind_vars={"id": str(node_id)})
                list(cursor)
            except Exception:
                pass

    def traversal_1hop(self, start_node_id: int) -> int:
        aql = """
        FOR v IN 1..1 ANY CONCAT('Developer/', @id) GRAPH 'github_graph'
        RETURN DISTINCT v._key
        """
        cursor = self.db.aql.execute(aql, bind_vars={"id": str(start_node_id)})
        return len(list(cursor))

    def traversal_2hop(self, start_node_id: int) -> int:
        aql = """
        FOR v IN 2..2 ANY CONCAT('Developer/', @id) GRAPH 'github_graph'
        RETURN DISTINCT v._key
        """
        cursor = self.db.aql.execute(aql, bind_vars={"id": str(start_node_id)})
        return len(list(cursor))

    def traversal_3hop(self, start_node_id: int) -> int:
        aql = """
        FOR v IN 3..3 ANY CONCAT('Developer/', @id) GRAPH 'github_graph'
        RETURN DISTINCT v._key
        """
        cursor = self.db.aql.execute(aql, bind_vars={"id": str(start_node_id)})
        return len(list(cursor))

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        aql = "RETURN DOCUMENT(CONCAT('Developer/', @id))"
        cursor = self.db.aql.execute(aql, bind_vars={"id": str(node_id)})
        doc = cursor.next() if cursor.has_more() or len(cursor) > 0 else None
        if doc:
            return {"id": doc.get("node_id"), "username": doc.get("username"), "developer_type": doc.get("developer_type")}
        return None

    def indexed_lookup(self, developer_type: str) -> int:
        aql = """
        FOR doc IN Developer
        FILTER doc.developer_type == @dev_type
        COLLECT WITH COUNT INTO cnt
        RETURN cnt
        """
        cursor = self.db.aql.execute(aql, bind_vars={"dev_type": str(developer_type)})
        return cursor.next() if cursor else 0

    def aggregation(self) -> List[Dict[str, Any]]:
        aql = """
        FOR doc IN Developer
        COLLECT type = doc.developer_type WITH COUNT INTO total
        SORT total DESC
        RETURN {dev_type: type, total: total}
        """
        cursor = self.db.aql.execute(aql)
        return list(cursor)

    def write_edge(self, source_id: int, target_id: int) -> bool:
        try:
            bench_col = self.db.collection("BenchTemp")
            bench_col.insert({
                "_from": f"Developer/{source_id}",
                "_to": f"Developer/{target_id}"
            }, silent=True)
            return True
        except Exception:
            return False

    def get_footprint(self) -> Dict[str, Any]:
        if not self.db:
            return {"status": "not connected"}
        try:
            stats = self.db.collection("Developer").figures()
            return {
                "engine": "Multi-Model Document + RocksDB Edge Index",
                "vertex_count": stats.get("documents_count"),
                "edge_count": self.db.collection("MutualFollow").figures().get("documents_count")
            }
        except Exception:
            return {
                "engine": "Multi-Model Document + RocksDB Edge Index",
                "stored_data_size": "RocksDB Disk SST files",
                "memory_usage": "Observable via ArangoGraph Portal"
            }
