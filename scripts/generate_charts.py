#!/usr/bin/env python3
"""
Publication-Quality Chart Generator
Generates clean, accurately labeled visualization charts from processed benchmark results.
"""

import logging
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SUMMARY_CSV = Path("results/processed/summary.csv")
CHARTS_DIR = Path("charts")

# Professional theme & styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "Arial", "DejaVu Sans", "Helvetica"
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

DB_COLORS = {
    "cognodb": "#1f77b4",     # Blue
    "neo4j": "#ff7f0e",       # Orange
    "memgraph": "#2ca02c",    # Green
    "falkordb": "#d62728",    # Red
    "arangodb": "#9467bd",    # Purple
    "kuzu": "#8c564b"         # Brown
}


def plot_traversal_latencies(df: pd.DataFrame) -> None:
    trav_df = df[df["workload"].isin(["traversal_1hop", "traversal_2hop", "traversal_3hop"])].copy()
    if trav_df.empty:
        return

    workload_map = {
        "traversal_1hop": "1-Hop",
        "traversal_2hop": "2-Hop",
        "traversal_3hop": "3-Hop"
    }
    trav_df["hop_label"] = trav_df["workload"].map(workload_map)

    # 1. p50 Latency Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=trav_df,
        x="hop_label",
        y="p50_ms",
        hue="database",
        palette=DB_COLORS,
        ax=ax
    )
    ax.set_title("Multi-Hop Neighborhood Traversal Latency (p50 Median)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Traversal Depth (Hops)", fontsize=12, labelpad=10)
    ax.set_ylabel("Latency (milliseconds) [Lower is Better]", fontsize=12, labelpad=10)
    ax.legend(title="Database", frameon=True)
    plt.tight_layout()
    chart_path = CHARTS_DIR / "traversal_latency_p50.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated {chart_path}")

    # 2. p95 Tail Latency Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=trav_df,
        x="hop_label",
        y="p95_ms",
        hue="database",
        palette=DB_COLORS,
        ax=ax
    )
    ax.set_title("Multi-Hop Neighborhood Traversal Latency (p95 Tail Latency)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Traversal Depth (Hops)", fontsize=12, labelpad=10)
    ax.set_ylabel("Latency (milliseconds) [Lower is Better]", fontsize=12, labelpad=10)
    ax.legend(title="Database", frameon=True)
    plt.tight_layout()
    chart_path = CHARTS_DIR / "traversal_latency_p95.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated {chart_path}")


def plot_lookups(df: pd.DataFrame) -> None:
    lookup_df = df[df["workload"].isin(["point_lookup", "indexed_lookup"])].copy()
    if lookup_df.empty:
        return

    workload_map = {
        "point_lookup": "Point Lookup (Primary Key)",
        "indexed_lookup": "Indexed Lookup (developer_type)"
    }
    lookup_df["lookup_type"] = lookup_df["workload"].map(workload_map)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=lookup_df,
        x="lookup_type",
        y="p50_ms",
        hue="database",
        palette=DB_COLORS,
        ax=ax
    )
    ax.set_title("Point Lookup vs. Indexed Lookup Latency (p50 Median)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Lookup Workload", fontsize=12, labelpad=10)
    ax.set_ylabel("Latency (milliseconds) [Lower is Better]", fontsize=12, labelpad=10)
    ax.legend(title="Database", frameon=True)
    plt.tight_layout()
    chart_path = CHARTS_DIR / "lookup_latency_p50.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated {chart_path}")


def plot_aggregation(df: pd.DataFrame) -> None:
    agg_df = df[df["workload"] == "aggregation"].copy()
    if agg_df.empty:
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))
    sns.barplot(
        data=agg_df,
        x="database",
        y="p50_ms",
        hue="database",
        palette=DB_COLORS,
        legend=False,
        ax=ax
    )
    ax.set_title("Full-Graph Aggregation Latency (Group-By Developer Category)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Database", fontsize=12, labelpad=10)
    ax.set_ylabel("Latency (milliseconds) [Lower is Better]", fontsize=12, labelpad=10)
    plt.tight_layout()
    chart_path = CHARTS_DIR / "aggregation_latency.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated {chart_path}")


def plot_concurrency_throughput(df: pd.DataFrame) -> None:
    conc_df = df[df["workload"].str.startswith("mixed_concurrency_c")].copy()
    if conc_df.empty:
        return

    # Extract concurrency integer from workload name
    conc_df["concurrency"] = conc_df["workload"].apply(lambda x: int(x.split("_c")[-1]))
    conc_df = conc_df.sort_values(by=["concurrency", "database"])

    fig, ax = plt.subplots(figsize=(10, 6))
    for db_name, group in conc_df.groupby("database"):
        color = DB_COLORS.get(db_name, "#333333")
        ax.plot(group["concurrency"], group["throughput_qps"], marker="o", linewidth=2.5, label=db_name, color=color)

    ax.set_title("Mixed Read/Write Concurrency Scaling (80% Read / 20% Write)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Client Concurrency (Worker Threads)", fontsize=12, labelpad=10)
    ax.set_ylabel("Throughput (Queries Per Second) [Higher is Better]", fontsize=12, labelpad=10)
    ax.legend(title="Database", frameon=True)
    plt.tight_layout()
    chart_path = CHARTS_DIR / "concurrency_vs_throughput.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated {chart_path}")


def generate_all_charts():
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    if not SUMMARY_CSV.exists():
        logger.warning(f"Summary file {SUMMARY_CSV} not found. Run benchmark first.")
        return

    df = pd.read_csv(SUMMARY_CSV)
    plot_traversal_latencies(df)
    plot_lookups(df)
    plot_aggregation(df)
    plot_concurrency_throughput(df)
    logger.info("All benchmark charts generated successfully in charts/")


if __name__ == "__main__":
    generate_all_charts()
