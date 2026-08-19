"""
Point and Indexed Lookup Workload Runner
Measures single key point lookup and filtered indexed property query latencies.
"""

import logging
from typing import Any, Dict, List, Tuple

from ..adapters.base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


def run_point_lookup_workload(
    adapter: BaseGraphAdapter,
    sample_node_ids: List[int],
    iterations: int = 100
) -> Tuple[List[float], float, int]:
    logger.info(f"[{adapter.name}] Running point lookup benchmark ({iterations} iterations)...")
    eval_nodes = sample_node_ids[:iterations]
    latencies_ms: List[float] = []
    errors = 0

    with HighResolutionTimer() as total_timer:
        for node_id in eval_nodes:
            timer = HighResolutionTimer()
            try:
                with timer:
                    adapter.point_lookup(node_id)
                latencies_ms.append(timer.elapsed_ms)
            except Exception as e:
                errors += 1
                logger.debug(f"[{adapter.name}] Point lookup error on node {node_id}: {e}")

    return latencies_ms, total_timer.elapsed_sec, errors


def run_indexed_lookup_workload(
    adapter: BaseGraphAdapter,
    iterations: int = 100
) -> Tuple[List[float], float, int]:
    logger.info(f"[{adapter.name}] Running indexed lookup benchmark ({iterations} iterations)...")
    latencies_ms: List[float] = []
    errors = 0
    categories = ["ml", "web"]

    with HighResolutionTimer() as total_timer:
        for i in range(iterations):
            cat = categories[i % len(categories)]
            timer = HighResolutionTimer()
            try:
                with timer:
                    adapter.indexed_lookup(cat)
                latencies_ms.append(timer.elapsed_ms)
            except Exception as e:
                errors += 1
                logger.debug(f"[{adapter.name}] Indexed lookup error on category {cat}: {e}")

    return latencies_ms, total_timer.elapsed_sec, errors
