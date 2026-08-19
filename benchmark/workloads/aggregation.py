"""
Graph Aggregation Workload Runner
Measures full-graph group-by count aggregation latencies.
"""

import logging
from typing import Any, Dict, List, Tuple

from ..adapters.base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


def run_aggregation_workload(
    adapter: BaseGraphAdapter,
    iterations: int = 100
) -> Tuple[List[float], float, int]:
    logger.info(f"[{adapter.name}] Running aggregation benchmark ({iterations} iterations)...")
    latencies_ms: List[float] = []
    errors = 0

    with HighResolutionTimer() as total_timer:
        for _ in range(iterations):
            timer = HighResolutionTimer()
            try:
                with timer:
                    res = adapter.aggregation()
                latencies_ms.append(timer.elapsed_ms)
            except Exception as e:
                errors += 1
                logger.debug(f"[{adapter.name}] Aggregation error: {e}")

    return latencies_ms, total_timer.elapsed_sec, errors
