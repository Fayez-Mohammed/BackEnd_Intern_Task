#!/usr/bin/env python3
"""
Dataset Downloader for WEXA AI Graph Database Benchmark
Downloads the SNAP musae-github (git_web_ml) dataset directly from official sources or verified mirrors.
"""

import os
import sys
import zipfile
import urllib.request
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

PRIMARY_ZIP_URL = "https://snap.stanford.edu/data/git_web_ml.zip"
FALLBACK_EDGES_URL = "https://raw.githubusercontent.com/benedekrozemberczki/datasets/master/musae_git_edges.csv"
FALLBACK_TARGET_URL = "https://raw.githubusercontent.com/benedekrozemberczki/datasets/master/musae_git_target.csv"


def download_file(url: str, dest_path: Path) -> bool:
    logger.info(f"Downloading from {url} to {dest_path}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "WEXA-Benchmark-Suite/1.0 (Research)"}
        )
        with urllib.request.urlopen(req, timeout=60) as response, open(dest_path, "wb") as out_file:
            total_size = int(response.info().get("Content-Length", -1))
            downloaded = 0
            block_size = 65536
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rDownloading: {percent:.1f}% ({downloaded / 1024 / 1024:.2f} MB)", end="", flush=True)
            print()
        logger.info(f"Successfully downloaded {dest_path.name} ({dest_path.stat().st_size / 1024 / 1024:.2f} MB)")
        return True
    except Exception as e:
        logger.error(f"Failed to download from {url}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    edges_raw = RAW_DIR / "musae_git_edges.csv"
    target_raw = RAW_DIR / "musae_git_target.csv"

    if edges_raw.exists() and target_raw.exists():
        logger.info("Raw dataset files already exist in data/raw. Skipping download.")
        return 0

    # Try ZIP download from SNAP Stanford first
    zip_path = RAW_DIR / "git_web_ml.zip"
    if download_file(PRIMARY_ZIP_URL, zip_path):
        try:
            logger.info("Extracting ZIP archive...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(RAW_DIR)
            
            # The ZIP might contain nested folder 'git_web_ml/'
            nested_folder = RAW_DIR / "git_web_ml"
            if nested_folder.exists() and nested_folder.is_dir():
                for f in nested_folder.iterdir():
                    dest = RAW_DIR / f.name
                    if dest.exists():
                        dest.unlink()
                    f.rename(dest)
                nested_folder.rmdir()
            logger.info("Extraction complete.")
            return 0
        except Exception as e:
            logger.warning(f"Error extracting ZIP archive: {e}. Falling back to direct raw CSV downloads.")

    # Fallback to direct raw CSV downloads from dataset author repository
    logger.info("Using verified raw CSV mirrors...")
    success_edges = download_file(FALLBACK_EDGES_URL, edges_raw)
    success_target = download_file(FALLBACK_TARGET_URL, target_raw)

    if success_edges and success_target:
        logger.info("All raw dataset files downloaded successfully.")
        return 0
    else:
        logger.error("Failed to acquire SNAP musae-github dataset.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
