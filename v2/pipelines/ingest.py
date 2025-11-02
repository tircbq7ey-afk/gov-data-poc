# v2/pipelines/ingest.py
from __future__ import annotations

from pathlib import Path
import argparse
import json
from typing import List, Dict, Any

# 同一パッケージのextract / Vector Store を利用
from . import extract
from app.store import vector


# このファイルから見てプロジェクトルート(v2/)を指す
ROOT = Path(__file__).resolve().parents[2]


def load_seed(path: Path) -> List[Dict[str, Any]]:
    """
    seed_urls.json を読み込む。
    - Windowsでよく混入する UTF-8 BOM を許容するため encoding='utf-8-sig' を使用
    - 最低限のキー正規化（欠損はデフォルト値を補完）
    返り値: [{"url": ..., "type": "pdf|html", "title": "...", "published_at": "...", "lang": "ja|en|..."}]
    """
    if not path.exists():
        raise FileNotFoundError(f"seed file not found: {path}")

    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("seed json must be a list of objects")

    normalized: List[Dict[str, Any]] = []
    for i, it in enumerate(data):
        if not isinstance(it, dict):
            # 無視して続行
            continue
        url = (it.get("url") or "").strip()
        if not url:
            # url必須。無いものはスキップ
            continue

        t = (it.get("type") or "").strip().lower()
        if t not in {"pdf", "html"}:
            # URL拡張子から推定（デフォルトはhtml）
            t = "pdf" if url.lower().endswith(".pdf") else "html"

        normalized.append(
            {
                "url": url,
                "type": t,
                "title": it.get("title", "").strip(),
                "published_at": it.get("published_at", "").strip(),
                "lang": (it.get("lang") or "ja").strip(),
            }
        )
    return normalized


def run(seed_file: Path) -> None:
    seeds = load_seed(seed_file)
    total_chunks = 0
    for s in seeds:
        # extract.build_docs は 1 seed dict -> List[Document] を想定
        docs = extract.build_docs(s)
        # VectorDB に upsert。返り値は書き込まれた chunk 数を想定
        total_chunks += vector.upsert(docs)

    print(f"ingest done: {len(seeds)} seeds, {total_chunks} chunks")


def _resolve_seed_path(arg_seed: str) -> Path:
    """
    引数が相対パスの場合は v2/ を基準に解決。
    絶対パス or v2/ から始まる文字列の両方に対応。
    """
    p = Path(arg_seed)
    if p.is_absolute():
        return p
    # 既に v2/ 配下の表記（.\\v2\\... や v2/...）もそのまま通す
    cand = (ROOT / p).resolve()
    return cand


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ingest pipeline")
    parser.add_argument(
        "--seed",
        type=str,
        required=True,
        help=r"Path to seed json (e.g. .\v2\pipelines\config\seed_urls.json)",
    )
    args = parser.parse_args()

    try:
        seed_path = _resolve_seed_path(args.seed)
        run(seed_path)
    except Exception as e:
        # 例外はわかりやすく1行で表示（WindowsのPowerShellでも読みやすい）
        print(f"[ingest:error] {type(e).__name__}: {e}")
        raise
