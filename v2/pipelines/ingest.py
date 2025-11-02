from __future__ import annotations
from pathlib import Path
import argparse
import json
from typing import List, Dict
from . import extract
from app.store import vector

ROOT = Path(__file__).resolve().parents[2]

def load_seed(path: Path) -> List[Dict]:
    # BOM付きでも読めるように 'utf-8-sig'
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    # 最低限の正規化
    norm = []
    for it in data:
        if not it.get("url"):
            continue
        norm.append({
            "url": it["url"],
            "type": it.get("type", "html"),
            "title": it.get("title", ""),
            "published_at": it.get("published_at", ""),
            "lang": it.get("lang", "ja"),
        })
    return norm

def run(seed_file: Path):
    seeds = load_seed(seed_file)
    total_docs = 0
    for s in seeds:
        docs = extract.build_docs(s)
        total_docs += vector.upsert(docs)
    print(f"ingest done: {len(seeds)} seeds, {total_docs} chunks")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=str, required=True)
    args = ap.parse_args()
    seed_path = (ROOT / args.seed) if not args.seed.startswith(str(ROOT)) else Path(args.seed)
    run(seed_path)
