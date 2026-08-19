"""
Graph Traversal Workload Runner
Executes 1-hop, 2-hop, and 3-hop neighborhood expansion benchmarks.
"""

import logging
from typing import Any, Dict, List, Tuple
from tqdm import tqdm

from ..adapters.base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


def run_traversal_workload(
    adapter: BaseGraphAdapter,
    sample_node_ids: List[int],
    warmup_iterations: int = 30,
    iterations: int = 100
) -> Dict[str, Tuple[List[float], float, int]]:
    """Runs 1-hop, 2-hop, and 3-hop traversals. Returns {hop_name: (latencies_ms, total_duration_sec, errors)}."""
    
    # 1. Warm-up Phase
    logger.info(f"[{adapter.name}] Warming up query plan caches ({warmup_iterations} iterations)...")
    adapter.warmup(sample_node_ids, iterations=warmup_iterations)

    eval_nodes = sample_node_ids[:iterations]
    results = {}

    for hop, func_name in [(1, "traversal_1hop"), (2, "traversal_2hop"), (3, "traversal_3hop")]:
        hop_key = f"traversal_{hop}hop"
        logger.info(f"[{adapter.name}] Running {hop_key} benchmark ({len(eval_nodes)} iterations)...")
        
        traversal_func = getattr(adapter, func_name)
        latencies_ms: List[float] = []
        errors = 0
        
        with HighResolutionTimer() as total_timer:
            for node_id in eval_nodes:
                timer = HighResolutionTimer()
                try:
                    with timer:
                        traversal_func(node_id)
                    latencies_ms.append(timer.elapsed_ms)
                except Exception as e:
                    errors += 1
                    logger.debug(f"[{adapter.name}] Error during {hop_key}({node_id}): {e}")

        total_sec = total_timer.elapsed_sec
        results[hop_key] = (latencies_ms, total_sec, errors)

    return results
