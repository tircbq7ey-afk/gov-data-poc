# v2/pipelines/ingest.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_SEED = "pipelines/config/seed_urls.json"

def load_seed(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"seed file not found: {p.resolve()}")

    raw = p.read_bytes()
    # tolerate UTF-8 BOM (EF BB BF)
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"failed to parse JSON: {p.resolve()}") from e

    if not isinstance(data, list):
        raise ValueError("seed must be a JSON array")

    norm: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"seed[{i}] must be an object")
        # normalize keys (optional)
        norm.append({
            "url": item.get("url", "").strip(),
            "type": item.get("type", "").strip(),
            "title": item.get("title", "").strip(),
            "lang": item.get("lang", "").strip() or "ja",
            "published_at": item.get("published_at", "").strip(),
        })
    return norm

def run(seed_path: str) -> None:
    seeds = load_seed(seed_path)
    print(f"[ingest] loaded {len(seeds)} seeds from {seed_path}")
    for s in seeds:
        print(f"  - {s['type']:4} | {s['url']}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=DEFAULT_SEED, help="path to seed_urls.json")
    args = ap.parse_args()
    run(args.seed)

if __name__ == "__main__":
    main()
