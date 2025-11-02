# v2/pipelines/ingest.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict

from app.store.vector import upsert  # PYTHONPATH=repo_root を前提

def load_seed(seed_path: Path) -> List[Dict]:
    """
    seed_urls.json を読み込む。UTF-8/BOM付きUTF-8 の両方に対応。
    """
    # Windows で作った JSON が BOM 付きでも読めるように utf-8-sig
    with seed_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def run(seed: Path) -> None:
    seeds = load_seed(seed)

    # 想定スキーマ: [{url, type, title, published_at, lang}]
    docs = []
    for s in seeds:
        docs.append({
            "url": s["url"],
            "type": s.get("type", "html"),
            "title": s.get("title", ""),
            "published_at": s.get("published_at", ""),
            "lang": s.get("lang", "ja"),
        })

    # ベクタストアへ投入（実装は app/store/vector.py 側）
    upsert(docs)
    print(f"[ingest] upserted={len(docs)} from {seed}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=str, default="v2/pipelines/config/seed_urls.json")
    args = p.parse_args()

    seed_path = Path(args.seed).resolve()
    if not seed_path.exists():
        raise FileNotFoundError(f"seed file not found: {seed_path}")

    run(seed_path)

if __name__ == "__main__":
    main()
