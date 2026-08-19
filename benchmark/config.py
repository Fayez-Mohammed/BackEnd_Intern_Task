"""
Configuration and Environment Management Module
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()


class BenchmarkConfig:
    def __init__(self, config_path: str = "config/benchmark.yaml"):
        self.config_path = Path(config_path)
        self.raw_config = self._load_yaml()

    def _load_yaml(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found at: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def random_seed(self) -> int:
        return int(self.raw_config.get("meta", {}).get("random_seed", 42))

    @property
    def dataset_config(self) -> Dict[str, Any]:
        return self.raw_config.get("dataset", {})

    @property
    def workloads_config(self) -> Dict[str, Any]:
        return self.raw_config.get("workloads", {})

    @property
    def databases_config(self) -> Dict[str, Any]:
        return self.raw_config.get("databases", {})

    @property
    def output_config(self) -> Dict[str, Any]:
        return self.raw_config.get("output", {})

    def get_database_env(self, db_key: str) -> Dict[str, str]:
        """Resolves environment variables for a given database."""
        db_meta = self.databases_config.get(db_key, {})
        prefix = db_meta.get("env_prefix", db_key.upper())
        
        env_vars = {}
        for key, val in os.environ.items():
            if key.startswith(f"{prefix}_"):
                suffix = key[len(f"{prefix}_"):]
                env_vars[suffix.lower()] = val
        return env_vars
