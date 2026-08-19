"""
Abstract Base Graph Database Adapter
Defines the uniform contract that every database adapter must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


class BaseGraphAdapter(ABC):
    def __init__(self, name: str, config: Dict[str, Any], env_vars: Dict[str, str]):
        self.name = name
        self.config = config
        self.env_vars = env_vars
        self.is_connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection / session pool with the database."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes all open connections and resources."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Performs basic connectivity check and measures baseline RTT ping."""
        pass

    @abstractmethod
    def clear_database(self) -> bool:
        """Deletes all graph nodes and edges to ensure clean benchmark state."""
        pass

    @abstractmethod
    def create_indexes(self) -> None:
        """Creates necessary primary and secondary indexes on Developer nodes."""
        pass

    @abstractmethod
    def load_nodes(self, df_nodes: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        """Loads nodes in batches. Returns (loaded_count, total_seconds)."""
        pass

    @abstractmethod
    def load_edges(self, df_edges: pd.DataFrame, batch_size: int = 1000) -> Tuple[int, float]:
        """Loads edges in batches. Returns (loaded_count, total_seconds)."""
        pass

    @abstractmethod
    def warmup(self, sample_node_ids: List[int], iterations: int = 30) -> None:
        """Pre-warms query plans and memory cache without recording metrics."""
        pass

    @abstractmethod
    def traversal_1hop(self, start_node_id: int) -> int:
        """Executes 1-hop neighborhood traversal. Returns neighbor count."""
        pass

    @abstractmethod
    def traversal_2hop(self, start_node_id: int) -> int:
        """Executes 2-hop neighborhood traversal. Returns reachable node count."""
        pass

    @abstractmethod
    def traversal_3hop(self, start_node_id: int) -> int:
        """Executes 3-hop neighborhood traversal. Returns reachable node count."""
        pass

    @abstractmethod
    def point_lookup(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Executes single point lookup by node_id. Returns node properties."""
        pass

    @abstractmethod
    def indexed_lookup(self, developer_type: str) -> int:
        """Executes filtered lookup on indexed property (e.g. developer_type='ml'). Returns count."""
        pass

    @abstractmethod
    def aggregation(self) -> List[Dict[str, Any]]:
        """Executes group-by aggregation (COUNT by developer_type)."""
        pass

    @abstractmethod
    def write_edge(self, source_id: int, target_id: int) -> bool:
        """Inserts a single edge (used in mixed read/write concurrency test)."""
        pass

    @abstractmethod
    def get_footprint(self) -> Dict[str, Any]:
        """Retrieves storage and memory footprint metrics if accessible."""
        pass
