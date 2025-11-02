# v2/pipelines/ingest.py
from __future__ import annotations

import os
import json
import hashlib
import datetime as dt
from pathlib import Path
from typing import Any, Dict, Iterable, List

# import from local packages
from app.store.vector import upsert
from pipelines.extract import extract_from_pdf, extract_from_html

# ====== Config ======
ROOT_DIR = Path(os.getenv("V2_ROOT", Path(__file__).resolve().parents[1]))  # v2/
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
SEED_PATH = Path(os.getenv("SEED_PATH", ROOT_DIR / "pipelines" / "config" / "seed_urls.json"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ====== Helpers ======
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _read_text_no_bom(p: Path) -> str:
    """
    Windows/PowerShell で作られた JSON が UTF-8 BOM/CRLF の場合でも確実に読めるようにする。
    """
    # utf-8-sig で BOM を吸収、EOL は \n に正規化
    txt = p.read_text(encoding="utf-8-sig")
    return txt.replace("\r\n", "\n").replace("\r", "\n")

def load_seed(path: Path) -> List[Dict[str, Any]]:
    """
    seed_urls.json の読み込みとバリデーション/補完。
    想定スキーマ:
      - url: str (必須)
      - type: "pdf"|"html" (任意: 拡張子で自動推定)
      - title: str (任意)
      - published_at: str (任意; YYYY-MM-DD など)
      - lang: str (任意; 既定 "ja")
    """
    if not path.exists():
        raise FileNotFoundError(f"seed file not found: {path}")

    raw = _read_text_no_bom(path)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(items, list):
        raise ValueError("seed must be a JSON array")

    norm: List[Dict[str, Any]] = []
    for i, row in enumerate(items, 1):
        if not isinstance(row, dict):
            print(f"[seed:{i}] skip (not an object)")
            continue

        url = (row.get("url") or "").strip()
        if not url:
            print(f"[seed:{i}] skip (missing url)")
            continue

        typ = (row.get("type") or "").lower().strip()
        if typ not in {"pdf", "html"}:
            # infer from url
            typ = "pdf" if url.lower().endswith(".pdf") else "html"

        title = (row.get("title") or "").strip() or ("出典" if typ == "pdf" else "")
        published_at = (row.get("published_at") or "").strip() or None
        lang = (row.get("lang") or "ja").strip() or "ja"

        norm.append({
            "url": url,
            "type": typ,
            "title": title,
            "published_at": published_at,
            "lang": lang,
        })
    return norm

def build_docs(seeds: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    extract_from_pdf / extract_from_html を使ってドキュメントを構築。
    """
    docs: List[Dict[str, Any]] = []
    crawled_at = dt.datetime.utcnow().strftime("%Y-%m-%d")

    for i, s in enumerate(seeds, 1):
        url = s["url"]
        typ = s["type"]
        try:
            if typ == "pdf":
                text = extract_from_pdf(url)
                title = s.get("title") or "出典"
            else:
                title, text = extract_from_html(url)
        except Exception as e:
            print(f"[{i}] extract error ({typ}): {url}\n  -> {e}")
            continue

        doc = {
            "id": sha256_hex(url),
            "text": (text or "")[:10000],  # 過大サイズ防止の暫定クリップ
            "meta": {
                "url": url,
                "title": title or "",
                "published_at": s.get("published_at"),
                "crawled_at": crawled_at,
                "lang": s.get("lang", "ja"),
            },
        }
        docs.append(doc)
    return docs

# ====== Entry point ======
def run() -> None:
    print(f"[ingest] seed: {SEED_PATH}")
    seeds = load_seed(SEED_PATH)
    if not seeds:
        print("[ingest] no seeds — nothing to do")
        return

    docs = build_docs(seeds)
    if not docs:
        print("[ingest] no docs extracted — nothing upserted")
        return

    upsert(docs)
    print(f"[ingest] upserted: {len(docs)} docs")

if __name__ == "__main__":
    # Windows で `python -m pipelines.ingest` 実行時に import が迷子にならないように保険
    os.environ.setdefault("PYTHONPATH", str(ROOT_DIR))
    run()
