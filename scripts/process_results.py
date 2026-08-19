#!/usr/bin/env python3
"""
Results Processor
Aggregates all raw JSON benchmark observations from results/raw/ and generates summary tables.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from tabulate import tabulate

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.metrics.stats import calculate_percentiles, summarize_latencies

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("results/raw")
PROCESSED_DIR = Path("results/processed")


def process_all_results():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    summaries: List[Dict[str, Any]] = []

    if not RAW_DIR.exists():
        logger.warning(f"Raw results directory {RAW_DIR} does not exist.")
        return

    for db_dir in RAW_DIR.iterdir():
        if db_dir.is_dir():
            db_name = db_dir.name
            for raw_file in db_dir.glob("*.json"):
                try:
                    with open(raw_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    workload = data.get("workload", raw_file.stem)
                    latencies = data.get("latencies_ms", [])
                    tot_sec = data.get("total_duration_sec", 0.0)
                    errors = data.get("errors", 0)
                    meta = data.get("metadata", {})

                    summary = summarize_latencies(
                        database=db_name,
                        workload=workload,
                        latencies_ms=latencies,
                        total_duration_sec=tot_sec,
                        errors=errors,
                        metadata=meta
                    )
                    summaries.append(summary)
                except Exception as e:
                    logger.error(f"Error processing {raw_file}: {e}")

    if not summaries:
        logger.warning("No valid raw result files found to process.")
        return

    df = pd.DataFrame(summaries)
    
    # Sort deterministically
    df = df.sort_values(by=["workload", "database"]).reset_index(drop=True)

    csv_path = PROCESSED_DIR / "summary.csv"
    json_path = PROCESSED_DIR / "summary.json"
    md_path = PROCESSED_DIR / "summary.md"

    # Flatten metadata for CSV
    csv_df = df.copy()
    if "metadata" in csv_df.columns:
        csv_df["metadata"] = csv_df["metadata"].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))

    csv_df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

    table_cols = ["database", "workload", "total_operations", "throughput_qps", "p50_ms", "p95_ms", "min_ms", "max_ms", "errors"]
    display_df = df[[col for col in table_cols if col in df.columns]]
    md_table = tabulate(display_df, headers="keys", tablefmt="github", showindex=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Comprehensive Graph Database Benchmark Summary Matrix\n\n{md_table}\n")

    logger.info(f"Processed {len(summaries)} workload observations successfully. Summary written to {md_path}")


if __name__ == "__main__":
    process_all_results()
