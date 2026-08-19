"""
Memgraph Database Adapter (Memgraph Cloud and Memgraph Community)
Connects to Memgraph via Bolt protocol using Cypher.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from neo4j import GraphDatabase, Driver

from .base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


class MemgraphAdapter(BaseGraphAdapter):
    def __init__(self, name: str, config: Dict[str, Any], env_vars: Dict[str, str]):
        super().__init__(name, config, env_vars)
        self.uri = env_vars.get("uri", "bolt://localhost:7688")
        self.user = env_vars.get("user", "")
        self.password = env_vars.get("password", "")
        self.database = env_vars.get("database", "memgraph")
        self.driver: Optional[Driver] = None

    def connect(self) -> bool:
        if not self.uri:
            logger.warning(f"[{self.name}] Missing MEMGRAPH_URI environment variable.")
            return False
        try:
            auth = (self.user, self.password) if (self.user and self.password) else None
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=auth,
                max_connection_lifetime=30 * 60,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0
            )
            self.driver.verify_connectivity()
            self.is_connected = True
            logger.info(f"[{self.name}] Successfully connected to {self.uri}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            self.is_connected = False
            return False

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.is_connected = False
            logger.info(f"[{self.name}] Driver closed.")

    def health_check(self) -> Dict[str, Any]:
        if not self.is_connected or not self.driver:
            return {"status": "unhealthy", "error": "Not connected"}
        try:
            with HighResolutionTimer() as timer:
                with self.driver.session() as session:
                    res = session.run("RETURN 1 AS ping").single()
                    val = res["ping"] if res else None
            return {
                "status": "healthy",
                "ping_rtt_ms": round(timer.elapsed_ms, 2),
                "response": val
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def clear_database(self) -> bool:
        if not self.driver:
            return False
        try:
            logger.info(f"[{self.name}] Clearing graph data in Memgraph...")
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info(f"[{self.name}] Database cleared successfully.")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to clear database: {e}")
            return False

    def create_indexes(self) -> None:
        if not self.driver:
            return
        logger.info(f"[{self.name}] Creating indexes on Developer(node_id) and Developer(developer_type)...")
        with self.driver.session() as session:
            try:
                session.run("CREATE INDEX ON :Developer(node_id)")
            except Exception as e:
                logger.warning(f"[{self.name}] Index on node_id notice: {e}")
            try:
                session.run("CREATE INDEX ON :Developer(developer_type)")
            except Exception as e:
                logger.warning(f"[{self.name}] Index on developer_type notice: {e}")

    def load_nodes(self, df_nodes: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.driver:
            return 0, 0.0
        total_loaded = 0
        records = df_nodes.to_dict(orient="records")
        start_time = time.perf_counter()

        query = """
        UNWIND $batch AS row
        CREATE (d:Developer {
            node_id: ToInteger(row.node_id),
            username: ToString(row.username),
            developer_type: ToString(row.developer_type)
        })
        """

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(query, batch=batch)
                total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def load_edges(self, df_edges: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        if not self.driver:
            return 0, 0.0
        total_loaded = 0
        records = df_edges.to_dict(orient="records")
        start_time = time.perf_counter()

        query = """
        UNWIND $batch AS row
        MATCH (src:Developer {node_id: ToInteger(row.source_id)})
        MATCH (tgt:Developer {node_id: ToInteger(row.target_id)})
        CREATE (src)-[:MUTUAL_FOLLOW]->(tgt)
        """

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(query, batch=batch)
                total_loaded += len(batch)

        elapsed = time.perf_counter() - start_time
        return total_loaded, elapsed

    def warmup(self, sample_node_ids: List[int], iterations: int = 30) -> None:
        if not self.driver:
            return
        logger.info(f"[{self.name}] Executing {iterations} warmup queries...")
        with self.driver.session() as session:
            for node_id in sample_node_ids[:iterations]:
                try:
                    session.run(
                        "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW]-(m:Developer) RETURN count(DISTINCT m)",
                        id=int(node_id)
                    ).consume()
                except Exception:
                    pass

    def traversal_1hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=int(start_node_id)).single()
            return result["cnt"] if result else 0

    def traversal_2hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*2]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=int(start_node_id)).single()
            return result["cnt"] if result else 0

    def traversal_3hop(self, start_node_id: int) -> int:
        query = "MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*3]-(m:Developer) RETURN count(DISTINCT m) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, id=int(start_node_id)).single()
            return result["cnt"] if result else 0

    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        query = "MATCH (n:Developer {node_id: $id}) RETURN n.node_id AS id, n.username AS username, n.developer_type AS developer_type"
        with self.driver.session() as session:
            result = session.run(query, id=int(node_id)).single()
            return dict(result) if result else None

    def indexed_lookup(self, developer_type: str) -> int:
        query = "MATCH (n:Developer {developer_type: $dev_type}) RETURN count(n) AS cnt"
        with self.driver.session() as session:
            result = session.run(query, dev_type=str(developer_type)).single()
            return result["cnt"] if result else 0

    def aggregation(self) -> List[Dict[str, Any]]:
        query = "MATCH (n:Developer) RETURN n.developer_type AS dev_type, count(n) AS total ORDER BY total DESC"
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def write_edge(self, source_id: int, target_id: int) -> bool:
        query = """
        MATCH (a:Developer {node_id: $src}), (b:Developer {node_id: $dst})
        CREATE (a)-[r:BENCH_TEMP]->(b)
        RETURN count(r) AS cnt
        """
        try:
            with self.driver.session() as session:
                session.run(query, src=int(source_id), dst=int(target_id)).consume()
                return True
        except Exception:
            return False

    def get_footprint(self) -> Dict[str, Any]:
        if not self.driver:
            return {"stored_data_size": "Not connected"}
        try:
            with self.driver.session() as session:
                res = session.run("SHOW STORAGE INFO").data()
                return {"storage_info": res}
        except Exception:
            return {
                "engine": "In-Memory C++ Engine",
                "stored_data_size": "In-Memory RAM buffer pool",
                "memory_usage": "Observable via Docker or Memgraph Cloud portal"
            }
