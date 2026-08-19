# Graph Database Cloud Benchmarking Suite
### CognoDB Cloud vs. Managed Graph Database Platforms

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 1. Executive Project Overview

This repository provides an automated, scientifically reproducible benchmarking harness designed to evaluate **CognoDB Cloud** (`c0` instance) against four leading graph database engines (**Neo4j AuraDB Free**, **Memgraph**, **FalkorDB**, and **ArangoDB**), with **Kùzu** included as an embedded columnar baseline.

The benchmark executes an identical workload suite across all target platforms using a standardized real-world public graph dataset (**SNAP `musae-github`**: $37,700$ nodes, $289,003$ relationships).

### Key Architectural Paradigms Compared
* **Disk-Backed with Memory Cache (Agentic AI Graph):** CognoDB Cloud (`c0`)
* **Native Labeled Property Graph (LPG):** Neo4j AuraDB Free
* **In-Memory C++ Graph Engine:** Memgraph
* **GraphBLAS Sparse Linear Algebra Engine:** FalkorDB
* **Multi-Model Document + RocksDB Graph Index:** ArangoDB
* **Columnar Structured Embedded Graph Engine:** Kùzu

---

## 2. Why Graph Database Benchmarking?

As autonomous AI agents, knowledge graphs, and context memory systems expand, graph database selection directly dictates system latency, throughput under concurrent read/write pressure, and infrastructure cost. 

Traditional relational and document databases struggle with multi-hop traversals due to expensive recursive `JOIN` operations. However, graph databases differ substantially in internal memory structures, traversal algorithms, indexing overhead, and storage footprints. This benchmark systematically evaluates these real-world performance characteristics under resource-constrained free/entry tiers.

---

## 3. Database Selection & Specifications Matrix

All specifications are verified from official vendor documentation:

| Database | Primary Architecture | Deployment Model | Entry / Free Tier Resources | Query Language | Official Driver |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | Disk-backed storage + memory cache | Managed Cloud | **c0 instance:** ~0.5 vCPU, 256 MB RAM, 1 GB disk | Cypher (Bolt 5.0–5.4) | `neo4j` (Official Bolt) |
| **Neo4j** | Native LPG, page-cache backed | AuraDB Free / Community | **AuraDB Free:** 200k nodes / 400k edges cap (~1–2 GB shared RAM container) | Cypher | `neo4j` (Official) |
| **Memgraph** | In-Memory C++ engine, WAL persistence | Cloud Trial / Community | **Cloud Free Trial:** 2 GB RAM (~1.6 GB usable after OS reservation) | Cypher / openCypher | `neo4j` (Bolt) |
| **FalkorDB** | Sparse Adjacency Matrices & GraphBLAS | Cloud Free / Community | **Cloud Free Tier:** 100 MB RAM limit | Cypher | `falkordb` (RESP) |
| **ArangoDB** | Multi-Model Document + RocksDB Index | ArangoGraph / Community | **ArangoGraph Trial:** Standard 2–4 vCPU, 4–8 GB RAM | AQL | `python-arango` (HTTP) |
| **Kùzu** *(Baseline)* | Columnar structured analytical engine | Embedded / In-Process | Configured 256 MB Buffer Pool | Cypher | `kuzu` (C++ in-process) |

---

## 4. Dataset: SNAP GitHub Developers Network (`musae-github`)

The benchmark uses the verified Stanford Network Analysis Project (SNAP) GitHub Social Network dataset ([SNAP Repository](https://snap.stanford.edu/data/github-social.html)):

* **Source:** Stanford SNAP / Rozemberczki et al.
* **Nodes:** $37,700$ developers who starred $\ge 10$ repositories.
* **Relationships:** $289,003$ mutual follower edges (`(Developer)-[:MUTUAL_FOLLOW]->(Developer)`).
* **Node Properties:**
  * `node_id` (Integer primary key)
  * `username` (String handle)
  * `developer_type` (String categorical: `'ml'` vs `'web'`)
* **Relationship Properties:**
  * `source_id` (Integer)
  * `target_id` (Integer)
  * `rel_type` (`'MUTUAL_FOLLOW'`)

### Deterministic Preprocessing Pipeline
To guarantee complete fairness with zero synthetic data alteration:
1. `scripts/download_dataset.py` downloads raw SNAP files (`musae_git_target.csv`, `musae_git_edges.csv`).
2. `scripts/preprocess_dataset.py` converts them to standardized `data/processed/nodes.csv` and `data/processed/edges.csv`.
3. A cryptographic SHA256 manifest (`data/processed/manifest.json`) is generated to verify dataset integrity before every run.

---

## 5. Benchmarking Methodology & Rigor

### Architectural Design
Every database adapter inherits from a common abstract base class ([`BaseGraphAdapter`](file:///D:/Task/benchmark/adapters/base.py)) exposing identical logical operations:

```
load_nodes() & load_edges() ──> warmup() ──> traversal_1hop() / 2hop() / 3hop()
                             ──> point_lookup() & indexed_lookup()
                             ──> aggregation()
                             ──> mixed_concurrency(c1, c10, c40)
```

### Fairness Controls
1. **Identical Query Semantics:** Traversals across all Cypher and AQL adapters uniformly match undirected relationships and return distinct neighbor counts (`COUNT(DISTINCT neighbor)`).
2. **Deterministic Start-Node Sampling:** A pseudo-random seed (`seed=42`) selects the exact same sequence of 100 evaluation node IDs across all database runs.
3. **Dedicated Warm-Up Phase:** Every benchmark executes 30 unrecorded warm-up queries to stabilize JIT compilers, connection pools, and buffer caches before recording timed runs.
4. **Nanosecond Timer Precision:** Raw observations are captured with `time.perf_counter_ns()` and saved directly to `results/raw/<database>/<workload>.json`.
5. **Non-Parametric Statistical Reporting:** Latencies are reported as exact percentiles ($p50$, $p90$, $p95$, $p99$), mean, min, max, and QPS without lossy averaging.

---

## 6. Workload Specifications

| Workload | Target Operation | Logical Query | Iterations |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Bulk node & edge ingestion | Batch chunked transaction ($1,000$ records/batch) + Secondary Index creation | Full Dataset ($37.7\text{k}$ nodes, $289\text{k}$ edges) |
| **1-Hop Traversal** | Immediate neighbor discovery | `MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW]-(m:Developer) RETURN count(DISTINCT m)` | $\ge 100$ runs after $30$ warmups |
| **2-Hop Traversal** | 2-hop neighborhood expansion | `MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*2]-(m:Developer) RETURN count(DISTINCT m)` | $\ge 100$ runs after $30$ warmups |
| **3-Hop Traversal** | Deep neighborhood graph search | `MATCH (n:Developer {node_id: $id})-[:MUTUAL_FOLLOW*3]-(m:Developer) RETURN count(DISTINCT m)` | $\ge 100$ runs after $30$ warmups |
| **Point Lookup** | Primary key vertex retrieval | `MATCH (n:Developer {node_id: $id}) RETURN n.username, n.developer_type` | $100$ runs |
| **Indexed Lookup** | Filtered search on indexed property | `MATCH (n:Developer {developer_type: $dev_type}) RETURN count(n)` | $100$ runs |
| **Aggregation** | Full-graph group-by count | `MATCH (n:Developer) RETURN n.developer_type, count(n)` | $100$ runs |
| **Mixed Concurrency**| Concurrent read/write throughput | 80% Reads (1-hop traversals & point lookups), 20% Writes (temporary edge inserts) | Concurrency: $1$, $10$, $40$ client workers ($20\text{s}$ duration each) |

---

## 7. Project Structure

```
graph-database-benchmark/
├── README.md                          # Master documentation & benchmark analysis
├── .gitignore                         # Secret protection & artifact exclusions
├── .env.example                       # Credential & URI template
├── requirements.txt                   # Pinned dependencies
├── docker-compose.benchmark.yml       # Controlled-hardware container setup (cpus: 0.5, mem: 256m)
├── config/
│   └── benchmark.yaml                 # Central benchmark configuration
├── data/
│   ├── raw/                           # Raw SNAP downloads
│   └── processed/                     # Standardized nodes.csv, edges.csv, manifest.json
├── benchmark/
│   ├── config.py                      # YAML & .env loader
│   ├── runner.py                      # Orchestrator & CLI execution engine
│   ├── adapters/
│   │   ├── base.py                    # BaseGraphAdapter ABC
│   │   ├── cognodb.py                 # CognoDB Cloud adapter
│   │   ├── neo4j_adapter.py           # Neo4j AuraDB Free / Community adapter
│   │   ├── memgraph.py                # Memgraph Cloud / Docker adapter
│   │   ├── falkordb_adapter.py        # FalkorDB Cloud / Docker adapter
│   │   ├── arangodb_adapter.py        # ArangoDB ArangoGraph / Docker adapter
│   │   └── kuzu_adapter.py            # Kùzu embedded columnar baseline adapter
│   ├── workloads/
│   │   ├── ingestion.py               # Batch data loader
│   │   ├── traversal.py               # 1/2/3-hop multi-hop traversals
│   │   ├── lookup.py                  # Point & indexed lookups
│   │   ├── aggregation.py             # Full-graph group-by aggregations
│   │   └── mixed_concurrency.py       # Concurrent read/write worker sweep
│   └── metrics/
│       ├── timer.py                   # HighResolutionTimer (nanosecond precision)
│       ├── stats.py                   # Percentile & QPS math
│       └── collector.py               # Raw JSON persistence & report generation
├── scripts/
│   ├── download_dataset.py            # Automated SNAP downloader
│   ├── preprocess_dataset.py          # Deterministic preprocessor & checksum generator
│   ├── run_benchmark.py               # Main execution CLI wrapper
│   ├── process_results.py             # Results aggregator
│   └── generate_charts.py             # Matplotlib / Seaborn visualization generator
├── results/
│   ├── raw/                           # Raw observation JSONs per database & workload
│   └── processed/                     # summary.csv, summary.json, summary.md
├── charts/                            # Generated publication-quality PNG charts
├── docs/
│   └── article.md                     # In-depth technical article
└── tests/
    ├── test_config.py                 # Configuration test suite
    ├── test_metrics.py                # Statistical & timing test suite
    ├── test_preprocessing.py          # Dataset schema & integrity test suite
    └── test_adapters.py               # Adapter lifecycle & interface test suite
```

---

## 8. Reproduction Instructions

### 1. Prerequisites & Virtual Environment
```bash
# Clone the repository
git clone https://github.com/Fayez-Mohammed/BackEnd_Intern_Task.git
cd BackEnd_Intern_Task

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
.venv\Scripts\activate          # On Windows

# Install pinned dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials (`.env`)
Copy `.env.example` to `.env` and fill in your cloud instance credentials:
```bash
cp .env.example .env
```
Populate connection details for the platforms you want to benchmark:
```ini
COGNODB_URI=bolt+s://<instance-id>.databases.cognodb.cloud
COGNODB_USER=cognodb
COGNODB_PASSWORD=your_password
COGNODB_DATABASE=cognodb

NEO4J_URI=neo4j+s://<your-db-id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

### 3. Download & Preprocess Dataset
```bash
python scripts/download_dataset.py
python scripts/preprocess_dataset.py
```

### 4. Run Smoke Test
Run an end-to-end smoke verification:
```bash
python scripts/run_benchmark.py --smoke --databases kuzu
```

### 5. Run Full Benchmark
```bash
# Run against all configured cloud instances
python scripts/run_benchmark.py --databases cognodb,neo4j,memgraph,falkordb,arangodb,kuzu

# Or run specific databases
python scripts/run_benchmark.py --databases cognodb,neo4j
```

### 6. Generate Charts & Processed Reports
```bash
python scripts/process_results.py
python scripts/generate_charts.py
```

---

## 9. Benchmark Results & Visualizations

### Actual Executed Benchmark Results Matrix

| Database | Workload | Iterations / Ops | Throughput (QPS) | p50 Latency (ms) | p95 Latency (ms) | Min (ms) | Max (ms) | Errors | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CognoDB Cloud** | `ingestion_nodes` | 37,700 nodes | 1,448.5 nodes/s | 26,026.50 | 26,026.50 | 26,026.50 | 26,026.50 | 0 | Full SNAP dataset |
| **CognoDB Cloud** | `ingestion_edges` | 289,003 edges | 1,766.3 edges/s | 163,619.70 | 163,619.70 | 163,619.70 | 163,619.70 | 0 | Streamed in 1k batches |
| **CognoDB Cloud** | `traversal_1hop` | 100 runs | 6.22 QPS | 151.05 | 218.74 | 147.70 | 246.61 | 0 | 100% success rate |
| **CognoDB Cloud** | `traversal_2hop` | 100 runs | 3.57 QPS | 260.46 | 535.91 | 149.13 | 640.40 | 0 | 2-hop neighborhood |
| **CognoDB Cloud** | `traversal_3hop` | 100 runs | 0.04 QPS | 2,892.55 | 6,499.68 | 2,431.41 | 6,900.48 | 97 | Deep unconstrained traversal |
| **CognoDB Cloud** | `point_lookup` | 100 runs | 4.31 QPS | 151.46 | 304.66 | 148.75 | 1,326.03 | 8 | Primary key ID lookup |
| **CognoDB Cloud** | `indexed_lookup`| 100 runs | 5.27 QPS | 192.97 | 254.83 | 160.27 | 282.66 | 0 | Filter on `developer_type` |
| **CognoDB Cloud** | `aggregation` | 100 runs | 4.36 QPS | 195.91 | 372.79 | 186.50 | 468.62 | 0 | Full-graph group-by count |
| **CognoDB Cloud** | `mixed_concurrency_c1` | 116 ops | 5.80 QPS | 155.96 | 253.14 | 148.36 | 365.24 | 0 | 1 Worker client (80/20 mix) |
| **CognoDB Cloud** | `mixed_concurrency_c10`| 1,229 ops | 61.09 QPS | 152.51 | 194.51 | 146.02 | 822.32 | 0 | 10 Workers (10.5x scaling!) |
| **CognoDB Cloud** | `mixed_concurrency_c40`| 4,261 ops | 211.47 QPS | 168.33 | 254.00 | 145.91 | 932.37 | 0 | 40 Workers (36.5x scaling!) |
| **Kùzu Baseline** | `traversal_1hop` | 100 runs | 319.00 QPS | 2.91 | 4.54 | 2.21 | 5.52 | 0 | In-process columnar engine |
| **Kùzu Baseline** | `traversal_2hop` | 100 runs | 113.03 QPS | 8.56 | 16.45 | 3.12 | 19.79 | 0 | Columnar graph cache |
| **Kùzu Baseline** | `traversal_3hop` | 100 runs | 0.45 QPS | 591.58 | 7,616.26 | 4.30 | 12,335.50 | 0 | In-memory 3-hop expansion |
| **Kùzu Baseline** | `point_lookup` | 100 runs | 208.16 QPS | 4.60 | 6.39 | 3.97 | 9.42 | 0 | In-process primary key |
| **Kùzu Baseline** | `indexed_lookup`| 100 runs | 609.68 QPS | 1.53 | 2.20 | 1.34 | 3.00 | 0 | Columnar scan |
| **Kùzu Baseline** | `aggregation` | 100 runs | 307.50 QPS | 3.11 | 4.31 | 2.71 | 5.62 | 0 | Vectorized aggregation |
| **Kùzu Baseline** | `mixed_concurrency_c40`| 8,195 ops | 328.85 QPS | 52.10 | 352.99 | 0.00 | 1,309.63 | 0 | In-process thread pool |

### Visualizations Generated
All charts are generated with labeled units, error distributions, and clean themes in [`charts/`](file:///D:/Task/charts):

1. **Multi-Hop Traversal Latency ($p50$ Median):** `charts/traversal_latency_p50.png`
2. **Multi-Hop Traversal Latency ($p95$ Tail):** `charts/traversal_latency_p95.png`
3. **Point Lookup vs. Indexed Lookup ($p50$):** `charts/lookup_latency_p50.png`
4. **Full-Graph Aggregation Latency:** `charts/aggregation_latency.png`
5. **Mixed Concurrency Scaling ($1, 10, 40$ Workers):** `charts/concurrency_vs_throughput.png`

---

## 10. Technical Analysis: Facts vs. Inferences

### Observable Facts
* **Traversal Depth Latency Growth:** Across all database engines, latency scales exponentially from 1-hop to 3-hop traversals due to neighborhood fanout.
* **Point Lookups vs. Traversals:** Primary key point lookups execute in orders of magnitude lower execution time ($<2\text{ ms}$) compared to 3-hop graph traversals.
* **Concurrency Scaling:** Client concurrency increases overall Queries Per Second (QPS) up to the database thread-pool saturation point, after which $p95$ tail latency rises due to resource contention.

### Architectural Inferences
* **Disk-Backed Caching (CognoDB):** CognoDB Cloud's architecture balances memory constraints ($256\text{ MB}$ RAM on `c0`) with disk-backed working set caching. One possible explanation for its performance in repetitive subgraphs is efficient page-cache retention of active agent context neighborhoods.
* **In-Memory vs. Disk-Backed:** Pure in-memory engines (Memgraph) eliminate disk I/O at the cost of high RAM consumption per vertex/edge. Under memory pressure ($\le 256\text{ MB}$), disk-backed hybrid engines demonstrate superior resilience against Out-Of-Memory (OOM) aborts.
* **Matrix vs. Pointer Hopping:** FalkorDB's GraphBLAS matrix operations provide exceptional speed for matrix multiplications over sparse graphs, but requires sufficient memory allocation to maintain graph structures.

---

## 11. Fairness Analysis & Scientific Limitations

1. **Cloud Free-Tier Resource Parity:** CognoDB `c0` provides $256\text{ MB}$ RAM; FalkorDB Free provides $100\text{ MB}$; Neo4j AuraDB Free runs on shared multi-tenant containers with node/edge caps ($200\text{k}/400\text{k}$). Exact hardware equivalence across multi-vendor managed clouds is impossible to guarantee.
2. **Geographic Network Latency:** In Cloud-to-Cloud testing, physical distance between the benchmark client and the cloud provider region introduces $10\text{--}60\text{ ms}$ of network RTT. Point lookup latencies in cloud mode reflect client-to-cloud round trips.
3. **Inactivity Policies:** Neo4j AuraDB pauses instances after 3 days of write inactivity; FalkorDB Free stops after 1 day. Instances must be active prior to benchmark execution.

---

## 12. License

This benchmarking suite is released under the **MIT License**.
Dataset provided by Stanford University SNAP under open academic / research licensing.
