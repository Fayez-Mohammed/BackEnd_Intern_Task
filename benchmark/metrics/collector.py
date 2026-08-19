"""
Metrics Collector
Collects raw observations, persists them to disk without loss, and generates structured summary outputs.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from tabulate import tabulate

from .stats import summarize_latencies

logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self, raw_dir: str = "results/raw", processed_dir: str = "results/processed"):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.summaries: List[Dict[str, Any]] = []

    def record_raw_observations(
        self,
        database: str,
        workload: str,
        latencies_ms: List[float],
        total_duration_sec: float,
        errors: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Saves raw observations to JSON and computes statistical summary."""
        db_raw_dir = self.raw_dir / database
        db_raw_dir.mkdir(parents=True, exist_ok=True)

        raw_filepath = db_raw_dir / f"{workload}.json"
        raw_data = {
            "database": database,
            "workload": workload,
            "total_duration_sec": total_duration_sec,
            "errors": errors,
            "sample_count": len(latencies_ms),
            "latencies_ms": latencies_ms,
            "metadata": metadata or {}
        }

        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)

        summary = summarize_latencies(
            database=database,
            workload=workload,
            latencies_ms=latencies_ms,
            total_duration_sec=total_duration_sec,
            errors=errors,
            metadata=metadata
        )
        self.summaries.append(summary)
        logger.info(
            f"[{database}] Workload '{workload}': "
            f"p50={summary['p50_ms']:.2f}ms, p95={summary['p95_ms']:.2f}ms, "
            f"ops={summary['total_operations']}, QPS={summary['throughput_qps']:.1f}"
        )
        return summary

    def generate_reports(self) -> Dict[str, Path]:
        """Generates summary.csv, summary.json, and summary.md."""
        if not self.summaries:
            logger.warning("No summaries recorded to generate reports.")
            return {}

        df = pd.DataFrame(self.summaries)

        # Flatten metadata column for CSV readability if present
        csv_df = df.copy()
        if "metadata" in csv_df.columns:
            csv_df["metadata"] = csv_df["metadata"].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))

        # 1. summary.csv
        csv_path = self.processed_dir / "summary.csv"
        csv_df.to_csv(csv_path, index=False)

        # 2. summary.json
        json_path = self.processed_dir / "summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.summaries, f, indent=2)

        # 3. summary.md
        table_cols = ["database", "workload", "total_operations", "throughput_qps", "p50_ms", "p95_ms", "min_ms", "max_ms", "errors"]
        display_df = df[[col for col in table_cols if col in df.columns]]
        md_table = tabulate(display_df, headers="keys", tablefmt="github", showindex=False)
        
        md_content = f"# Benchmark Execution Summary Matrix\n\nGenerated from raw observations.\n\n{md_table}\n"
        md_path = self.processed_dir / "summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Summary reports generated: CSV={csv_path}, JSON={json_path}, Markdown={md_path}")
        return {
            "csv": csv_path,
            "json": json_path,
            "markdown": md_path
        }
