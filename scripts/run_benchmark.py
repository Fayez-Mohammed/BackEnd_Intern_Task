#!/usr/bin/env python3
"""
Convenience CLI Script for Running Benchmarks
Usage:
    python scripts/run_benchmark.py --smoke --databases kuzu
    python scripts/run_benchmark.py --databases cognodb,neo4j,memgraph,falkordb,arangodb
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.runner import main

if __name__ == "__main__":
    main()
