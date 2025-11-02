# v2/pipelines/ingest.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

# ベクタ格納が未実装でも動くようにoptional import
try:
    from app.store.vector import upsert  # type: ignore
except Exception:
    upsert = None  # ダミー

def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    """
    seed_urls.json を読み込む。UTF-8 with/without BOM の両方対応。
    """
    if not seed_path.exists():
        raise FileNotFoundError(f"seed file not found: {seed_path}")
    with seed_path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("seed file must be a JSON array")
    # 必須キーの薄いバリデーション
    required = {"url", "type", "title", "lang"}
    for i, item in enumerate(data):
        if not isinstance(item, dict) or not required.issubset(item.keys()):
            raise ValueError(f"seed[{i}] missing keys, required={required}")
    return data

def run(seed_file: str) -> None:
    seed_path = Path(seed_file).resolve()
    seeds = load_seed(seed_path)
    print(f"[ingest] loaded {len(seeds)} seeds from {seed_path}")

    # upsert が用意されている環境のみ実行（なければドライラン）
    if upsert is None:
        print("[ingest] 'app.store.vector.upsert' not found -> dry-run only.")
        for s in seeds:
            print(f"  - {s['type']:4s} | {s['lang']} | {s['title']} | {s['url']}")
        return

    # ここに実際の取得→分割→埋め込み→upsert をつなぐ
    # まずはURLメタだけを upsert するダミー実装（後で実体化）
    payloads = []
    for s in seeds:
        payloads.append({
            "doc_id": s["url"],
            "chunks": [{"chunk_id": f"{s['url']}#0", "text": s["title"]}],
            "meta": {"type": s["type"], "lang": s["lang"], "title": s["title"], "source": s["url"]},
        })
    upsert(payloads)
    print(f"[ingest] upserted {len(payloads)} docs.")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=str(Path("v2/pipelines/config/seed_urls.json")))
    args = ap.parse_args()
    run(args.seed)

if __name__ == "__main__":
    main()
