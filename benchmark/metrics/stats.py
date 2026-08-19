"""
Statistical Calculations for Benchmark Observations
Calculates accurate non-parametric percentiles (p50, p90, p95, p99), mean, stddev, min, max, throughput.
"""

from typing import Dict, List, Any
import numpy as np


def calculate_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    """Calculates non-parametric percentiles from raw observation list."""
    if not latencies_ms:
        return {
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "mean_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "stddev_ms": 0.0,
            "count": 0
        }

    arr = np.array(latencies_ms)
    return {
        "p50_ms": float(np.percentile(arr, 50)),
        "p90_ms": float(np.percentile(arr, 90)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "mean_ms": float(np.mean(arr)),
        "min_ms": float(np.min(arr)),
        "max_ms": float(np.max(arr)),
        "stddev_ms": float(np.std(arr)),
        "count": len(latencies_ms)
    }


def summarize_latencies(
    database: str,
    workload: str,
    latencies_ms: List[float],
    total_duration_sec: float,
    errors: int = 0,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Summarizes a workload run into a structured metric dictionary."""
    stats = calculate_percentiles(latencies_ms)
    count = stats["count"]
    throughput_qps = (count / total_duration_sec) if total_duration_sec > 0 else 0.0

    result = {
        "database": database,
        "workload": workload,
        "total_duration_sec": round(total_duration_sec, 4),
        "total_operations": count,
        "errors": errors,
        "throughput_qps": round(throughput_qps, 2),
        **stats,
        "metadata": metadata or {}
    }
    return result
