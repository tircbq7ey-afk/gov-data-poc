# pipelines/ingest.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# 既存の実装を呼び出すプロジェクト固有コードがある場合はここで import
# 例）from app.store.vector import upsert
# いったんダミー関数で置き、既存環境に合わせて差し替え可
def upsert(texts: List[str], metadatas: List[Dict[str, Any]]) -> None:
    # ここは既存のベクトルDB登録処理に差し替えてください
    print(f"[ingest] upsert {len(texts)} chunks")

def read_text_from_pdf(url: str) -> str:
    # 必要ならpdfminer / PyMuPDF へ差し替え
    # 最小実装：ダウンロード済みパスをテキストとして扱う（PoC向け）
    return f"[PDF placeholder] {url}"

def read_text_from_html(url: str) -> str:
    # 必要なら requests+BS4 で本文抽出に差し替え
    return f"[HTML placeholder] {url}"

def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    if not seed_path.exists():
        raise FileNotFoundError(f"seed file not found: {seed_path}")
    # ★ UTF-8 BOM 恒久対策：utf-8-sig で読む（BOMの有無どちらでもOK）
    with seed_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def run(seed: Path) -> None:
    seeds = load_seed(seed)

    texts: List[str] = []
    metas: List[Dict[str, Any]] = []

    for i, item in enumerate(seeds):
        url = item.get("url")
        typ = (item.get("type") or "").lower()
        title = item.get("title") or ""
        lang = item.get("lang") or "ja"
        published_at = item.get("published_at") or ""

        if not url or not typ:
            print(f"[warn] skip #{i}: missing url/type -> {item}")
            continue

        if typ == "pdf":
            text = read_text_from_pdf(url)
        elif typ == "html":
            text = read_text_from_html(url)
        else:
            print(f"[warn] skip #{i}: unknown type '{typ}' -> {item}")
            continue

        if not text:
            print(f"[warn] empty text #{i} for {url}")
            continue

        texts.append(text)
        metas.append(
            {
                "url": url,
                "title": title,
                "lang": lang,
                "published_at": published_at,
                "source_type": typ,
            }
        )

    if not texts:
        print("[ingest] no texts to upsert; finished.")
        return

    upsert(texts, metas)
    print(f"[ingest] done. upserted={len(texts)}")

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="GovDocs ingest")
    parser.add_argument(
        "--seed",
        required=True,
        help=r"Path to seed_urls.json (relative or absolute). "
             r"例: --seed .\v2\pipelines\config\seed_urls.json",
    )
    args = parser.parse_args(argv)

    # ★ パス安定化：現在位置からの相対/絶対どちらでも解決
    seed_path = Path(args.seed).expanduser().resolve()
    try:
        run(seed_path)
        return 0
    except FileNotFoundError as e:
        print(f"[error] {e}")
        return 2
    except json.JSONDecodeError as e:
        # BOMや不正JSONを捕捉してヒントを出す
        print(f"[error] JSON decode failed: {e}")
        print("ヒント: PowerShellで作成する場合は UTF-8/UTF-8(BOM) いずれでもOK（コード側で吸収）")
        return 3

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
