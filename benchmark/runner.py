"""
Central Benchmark Harness and Orchestrator
Executes all benchmark suites across specified database adapters deterministically.
"""

import argparse
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from .config import BenchmarkConfig
from .adapters import ADAPTER_MAP, BaseGraphAdapter
from .metrics.collector import MetricsCollector
from .workloads import (
    run_ingestion_workload,
    run_traversal_workload,
    run_point_lookup_workload,
    run_indexed_lookup_workload,
    run_aggregation_workload,
    run_concurrency_sweep
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("benchmark.runner")


class BenchmarkRunner:
    def __init__(self, config_path: str = "config/benchmark.yaml", smoke_mode: bool = False):
        self.config = BenchmarkConfig(config_path)
        self.smoke_mode = smoke_mode
        self.collector = MetricsCollector(
            raw_dir=self.config.output_config.get("raw_dir", "results/raw"),
            processed_dir=self.config.output_config.get("processed_dir", "results/processed")
        )
        self.nodes_df: Optional[pd.DataFrame] = None
        self.edges_df: Optional[pd.DataFrame] = None
        self.sample_node_ids: List[int] = []

    def prepare_data(self) -> None:
        """Loads and prepares standardized dataset and deterministic sample nodes."""
        nodes_path = Path(self.config.dataset_config.get("nodes_file", "data/processed/nodes.csv"))
        edges_path = Path(self.config.dataset_config.get("edges_file", "data/processed/edges.csv"))

        if not nodes_path.exists() or not edges_path.exists():
            raise FileNotFoundError(
                f"Processed dataset files missing. Please run 'python scripts/preprocess_dataset.py' first."
            )

        logger.info(f"Loading dataset from {nodes_path} and {edges_path}...")
        self.nodes_df = pd.read_csv(nodes_path)
        self.edges_df = pd.read_csv(edges_path)

        if self.smoke_mode:
            logger.info("SMOKE MODE: Truncating dataset to 2,000 nodes and 5,000 edges for rapid validation.")
            self.nodes_df = self.nodes_df.iloc[:2000].copy()
            valid_node_ids = set(self.nodes_df["node_id"])
            self.edges_df = self.edges_df[
                self.edges_df["source_id"].isin(valid_node_ids) &
                self.edges_df["target_id"].isin(valid_node_ids)
            ].iloc[:5000].copy()

        # Deterministic node sampling for identical query sequence
        seed = self.config.random_seed
        rng = random.Random(seed)
        all_ids = self.nodes_df["node_id"].tolist()
        sample_count = min(100 if not self.smoke_mode else 10, len(all_ids))
        self.sample_node_ids = rng.sample(all_ids, sample_count)
        logger.info(f"Sampled {len(self.sample_node_ids)} deterministic query nodes (seed={seed}).")

    def run_adapter_benchmarks(self, db_key: str, skip_ingest: bool = False) -> None:
        if db_key not in ADAPTER_MAP:
            logger.error(f"Unknown database adapter '{db_key}'. Available: {list(ADAPTER_MAP.keys())}")
            return

        db_config = self.config.databases_config.get(db_key, {})
        env_vars = self.config.get_database_env(db_key)
        adapter_cls = ADAPTER_MAP[db_key]
        adapter: BaseGraphAdapter = adapter_cls(name=db_key, config=db_config, env_vars=env_vars)

        logger.info(f"\n{'='*70}\nSTARTING BENCHMARK FOR: {db_config.get('display_name', db_key)}\n{'='*70}")
        
        if not adapter.connect():
            logger.error(f"[{db_key}] Could not establish connection. Skipping.")
            return

        health = adapter.health_check()
        logger.info(f"[{db_key}] Health check: {health}")
        if health.get("status") != "healthy":
            logger.error(f"[{db_key}] Database is unhealthy. Aborting runs for this adapter.")
            adapter.close()
            return

        try:
            # 1. Ingestion Benchmark
            if not skip_ingest:
                batch_size = self.config.workloads_config.get("ingestion", {}).get("batch_size", 1000)
                ingest_metrics = run_ingestion_workload(
                    adapter=adapter,
                    df_nodes=self.nodes_df,
                    df_edges=self.edges_df,
                    batch_size=batch_size
                )
                self.collector.record_raw_observations(
                    database=db_key,
                    workload="ingestion_nodes",
                    latencies_ms=[ingest_metrics["node_load_time_sec"] * 1000.0],
                    total_duration_sec=ingest_metrics["node_load_time_sec"],
                    metadata={"items_loaded": ingest_metrics["nodes_loaded"], "items_per_sec": ingest_metrics["nodes_per_sec"]}
                )
                self.collector.record_raw_observations(
                    database=db_key,
                    workload="ingestion_edges",
                    latencies_ms=[ingest_metrics["edge_load_time_sec"] * 1000.0],
                    total_duration_sec=ingest_metrics["edge_load_time_sec"],
                    metadata={"items_loaded": ingest_metrics["edges_loaded"], "items_per_sec": ingest_metrics["edges_per_sec"]}
                )

            # 2. Multi-hop Traversals
            warmup_iters = 5 if self.smoke_mode else self.config.workloads_config.get("warmup", {}).get("iterations", 30)
            trav_iters = 10 if self.smoke_mode else self.config.workloads_config.get("traversals", {}).get("iterations", 100)

            traversal_results = run_traversal_workload(
                adapter=adapter,
                sample_node_ids=self.sample_node_ids,
                warmup_iterations=warmup_iters,
                iterations=trav_iters
            )
            for hop_key, (lats, tot_sec, errs) in traversal_results.items():
                self.collector.record_raw_observations(
                    database=db_key,
                    workload=hop_key,
                    latencies_ms=lats,
                    total_duration_sec=tot_sec,
                    errors=errs
                )

            # 3. Lookups
            lookup_iters = 10 if self.smoke_mode else self.config.workloads_config.get("lookups", {}).get("iterations", 100)
            pt_lats, pt_sec, pt_errs = run_point_lookup_workload(
                adapter=adapter,
                sample_node_ids=self.sample_node_ids,
                iterations=lookup_iters
            )
            self.collector.record_raw_observations(
                database=db_key,
                workload="point_lookup",
                latencies_ms=pt_lats,
                total_duration_sec=pt_sec,
                errors=pt_errs
            )

            idx_lats, idx_sec, idx_errs = run_indexed_lookup_workload(
                adapter=adapter,
                iterations=lookup_iters
            )
            self.collector.record_raw_observations(
                database=db_key,
                workload="indexed_lookup",
                latencies_ms=idx_lats,
                total_duration_sec=idx_sec,
                errors=idx_errs
            )

            # 4. Aggregation
            agg_iters = 10 if self.smoke_mode else self.config.workloads_config.get("aggregation", {}).get("iterations", 100)
            agg_lats, agg_sec, agg_errs = run_aggregation_workload(
                adapter=adapter,
                iterations=agg_iters
            )
            self.collector.record_raw_observations(
                database=db_key,
                workload="aggregation",
                latencies_ms=agg_lats,
                total_duration_sec=agg_sec,
                errors=agg_errs
            )

            # 5. Mixed Concurrency Sweep
            mixed_cfg = self.config.workloads_config.get("mixed", {})
            concurrency_levels = [1, 2] if self.smoke_mode else mixed_cfg.get("concurrency_levels", [1, 10, 40])
            duration_sec = 3.0 if self.smoke_mode else float(mixed_cfg.get("duration_seconds", 20.0))
            read_ratio = float(mixed_cfg.get("read_write_ratio", 0.80))

            concurrency_results = run_concurrency_sweep(
                adapter=adapter,
                sample_node_ids=self.sample_node_ids,
                concurrency_levels=concurrency_levels,
                read_write_ratio=read_ratio,
                duration_sec=duration_sec
            )
            for conc_key, (lats, tot_sec, errs, concurrency) in concurrency_results.items():
                self.collector.record_raw_observations(
                    database=db_key,
                    workload=conc_key,
                    latencies_ms=lats,
                    total_duration_sec=tot_sec,
                    errors=errs,
                    metadata={"concurrency": concurrency, "read_write_ratio": read_ratio}
                )

            # 6. Footprint
            footprint = adapter.get_footprint()
            logger.info(f"[{db_key}] Resource footprint: {footprint}")

        finally:
            adapter.close()

    def run_all(self, database_keys: List[str], skip_ingest: bool = False) -> None:
        self.prepare_data()
        for db_key in database_keys:
            self.run_adapter_benchmarks(db_key.strip(), skip_ingest=skip_ingest)
        self.collector.generate_reports()


def main():
    parser = argparse.ArgumentParser(description="WEXA AI Graph Database Benchmark Runner")
    parser.add_argument(
        "--databases",
        type=str,
        default="kuzu",
        help="Comma-separated list of database keys to benchmark (e.g. cognodb,neo4j,memgraph,falkordb,arangodb,kuzu)"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run fast smoke test with small subset of queries"
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip data ingestion step if database is already populated"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/benchmark.yaml",
        help="Path to YAML configuration file"
    )

    args = parser.parse_args()
    db_keys = [k.strip() for k in args.databases.split(",") if k.strip()]

    runner = BenchmarkRunner(config_path=args.config, smoke_mode=args.smoke)
    runner.run_all(database_keys=db_keys, skip_ingest=args.skip_ingest)


if __name__ == "__main__":
    main()
