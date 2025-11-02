# v2/pipelines/ingest.py
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# v2 ディレクトリを PYTHONPATH に入れて実行する前提
# 例: PS> $env:PYTHONPATH = (Get-Location).Path
from app.store.vector import upsert  # your vector store upsert
# upsert(items: List[Dict[str, Any]]) を想定。items は各ドキュメントメタデータの配列。

def load_seed(path: Path) -> List[Dict[str, Any]]:
    """
    seed_urls.json を読み込む。UTF-8 BOM を含む場合でも読み取れるよう utf-8-sig で開く。
    """
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("seed file must be a JSON array")
    return data

def normalize(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    スキーマ正規化：
    - 必須: url, type(html|pdf), title
    - 任意: published_at, lang(default 'ja')
    """
    url = (item.get("url") or "").strip()
    title = (item.get("title") or "").strip()
    typ = (item.get("type") or "").strip().lower()
    published_at = (item.get("published_at") or "").strip()
    lang = (item.get("lang") or "ja").strip().lower()

    if not url or not title:
        raise ValueError(f"invalid seed item (url/title missing): {item}")
    if typ not in ("html", "pdf"):
        # URL から推定（簡易）
        typ = "pdf" if url.lower().endswith(".pdf") else "html"

    return {
        "url": url,
        "type": typ,
        "title": title,
        "published_at": published_at,
        "lang": lang,
    }

def run(seed_path: Path) -> None:
    seeds_raw = load_seed(seed_path)
    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(seeds_raw):
        try:
            items.append(normalize(raw))
        except Exception as e:
            print(f"[skip #{idx}] {e}", file=sys.stderr)

    if not items:
        print("no valid seeds, nothing to upsert.")
        return

    # ベクターストアへ投入（中でクロール/抽出までやる想定の upsert）
    upsert(items)
    print(f"ingest done: {len(items)} items")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=str, required=True,
                    help="path to seed_urls.json")
    args = ap.parse_args()
    seed_path = Path(args.seed).resolve()
    if not seed_path.exists():
        raise FileNotFoundError(seed_path)
    run(seed_path)

if __name__ == "__main__":
    main()
