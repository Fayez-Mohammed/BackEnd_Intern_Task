"""
Database Adapters Package
"""

from .base import BaseGraphAdapter
from .cognodb import CognoDBAdapter
from .neo4j_adapter import Neo4jAdapter
from .memgraph import MemgraphAdapter
from .falkordb_adapter import FalkorDBAdapter
from .arangodb_adapter import ArangoDBAdapter
from .kuzu_adapter import KuzuAdapter

ADAPTER_MAP = {
    "cognodb": CognoDBAdapter,
    "neo4j": Neo4jAdapter,
    "memgraph": MemgraphAdapter,
    "falkordb": FalkorDBAdapter,
    "arangodb": ArangoDBAdapter,
    "kuzu": KuzuAdapter
}

__all__ = [
    "BaseGraphAdapter",
    "CognoDBAdapter",
    "Neo4jAdapter",
    "MemgraphAdapter",
    "FalkorDBAdapter",
    "ArangoDBAdapter",
    "KuzuAdapter",
    "ADAPTER_MAP"
]
