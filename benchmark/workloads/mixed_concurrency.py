"""
Mixed Read/Write Concurrency Workload Runner
Executes concurrent transactions across a sweep of client workers (1, 10, 40).
Workload Mix: 80% Reads (Traversals & Point Lookups), 20% Writes (Temporary Edge Inserts).
"""

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from ..adapters.base import BaseGraphAdapter
from ..metrics.timer import HighResolutionTimer

logger = logging.getLogger(__name__)


def _worker_task(
    adapter: BaseGraphAdapter,
    sample_node_ids: List[int],
    read_ratio: float,
    duration_sec: float,
    worker_id: int
) -> Tuple[List[float], int]:
    """Worker loop executing read/write transactions for duration_sec."""
    latencies_ms: List[float] = []
    errors = 0
    rng = random.Random(42 + worker_id)
    n_samples = len(sample_node_ids)

    end_time = time.perf_counter() + duration_sec
    while time.perf_counter() < end_time:
        is_read = rng.random() < read_ratio
        u_idx = rng.randint(0, n_samples - 1)
        src_id = sample_node_ids[u_idx]

        timer = HighResolutionTimer()
        try:
            with timer:
                if is_read:
                    # 50% 1-hop traversal, 50% point lookup
                    if rng.random() < 0.5:
                        adapter.traversal_1hop(src_id)
                    else:
                        adapter.point_lookup(src_id)
                else:
                    dst_idx = (u_idx + 1) % n_samples
                    dst_id = sample_node_ids[dst_idx]
                    adapter.write_edge(src_id, dst_id)
            latencies_ms.append(timer.elapsed_ms)
        except Exception:
            errors += 1
            time.sleep(0.01)

    return latencies_ms, errors


def run_concurrency_sweep(
    adapter: BaseGraphAdapter,
    sample_node_ids: List[int],
    concurrency_levels: List[int] = [1, 10, 40],
    read_write_ratio: float = 0.80,
    duration_sec: float = 20.0
) -> Dict[str, Tuple[List[float], float, int, int]]:
    """
    Runs mixed read/write concurrency sweep.
    Returns {f"mixed_concurrency_c{c}": (all_latencies_ms, total_duration_sec, total_errors, concurrency)}
    """
    results = {}
    for concurrency in concurrency_levels:
        workload_key = f"mixed_concurrency_c{concurrency}"
        logger.info(
            f"[{adapter.name}] Running {workload_key}: "
            f"concurrency={concurrency}, read_ratio={read_write_ratio:.0%}, duration={duration_sec}s..."
        )

        all_latencies: List[float] = []
        total_errors = 0

        with HighResolutionTimer() as total_timer:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(
                        _worker_task,
                        adapter,
                        sample_node_ids,
                        read_write_ratio,
                        duration_sec,
                        i
                    )
                    for i in range(concurrency)
                ]
                for fut in as_completed(futures):
                    worker_latencies, worker_errs = fut.result()
                    all_latencies.extend(worker_latencies)
                    total_errors += worker_errs

        total_sec = total_timer.elapsed_sec
        results[workload_key] = (all_latencies, total_sec, total_errors, concurrency)

    return results
