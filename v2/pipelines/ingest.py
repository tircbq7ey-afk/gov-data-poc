# -*- coding: utf-8 -*-
"""
RAG用インジェスト（Windows/PowerShellでもBOM混在を安全に読める版）
- --seed でJSONの場所を指定（省略時は pipelines/config/seed_urls.json）
- UTF-8 BOM/NoBOMのどちらでも読める
- 実行ディレクトリに依存しない堅牢なパス解決
"""
from __future__ import annotations
import os, sys, json, hashlib, datetime, logging
from pathlib import Path
from typing import Any, List, Dict, Tuple

# ------- ログ設定 -------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("ingest")

# ------- 依存モジュール -------
from app.store.vector import upsert            # 既存のupsertを利用
from pipelines.extract import (                # 既存の抽出関数を利用
    extract_from_pdf, extract_from_html
)

# ------- 定数 -------
PROJECT_ROOT = Path(__file__).resolve().parents[1]     # <repo>/pipelines/ingest.py -> <repo>
DEFAULT_SEED = PROJECT_ROOT / "pipelines" / "config" / "seed_urls.json"
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ------- ユーティリティ -------
def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _read_json_bom_tolerant(p: Path) -> Any:
    """
    UTF-8 BOM/NoBOM を両方受け付ける安全なJSON読込。
    """
    # まずバイナリで読み、BOMなら剥がしてからデコード
    b = p.read_bytes()
    if b.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM
        text = b[len(b"\xef\xbb\xbf"):].decode("utf-8")
    else:
        # 通常UTF-8として解釈。万一decode失敗したら 'utf-8-sig' にフォールバック
        try:
            text = b.decode("utf-8")
        except UnicodeDecodeError:
            text = b.decode("utf-8-sig")
    return json.loads(text)

def _resolve_seed_path(seed_arg: str | None) -> Path:
    """
    seed_arg が相対/絶対/バックスラッシュ混在でも実体Pathに解決。
    省略時は DEFAULT_SEED。
    """
    if not seed_arg:
        return DEFAULT_SEED

    # 引用符を除去（PowerShellの `".\v2\..."` などを安全に）
    s = seed_arg.strip().strip('"').strip("'")
    p = Path(s)

    # 実体化（相対なら現在位置基準 → 存在しなければプロジェクトルート基準を試す）
    if p.exists():
        return p.resolve()

    # repoルート基準の再解決を試行
    maybe = (PROJECT_ROOT / p).resolve()
    if maybe.exists():
        return maybe

    raise FileNotFoundError(f"seed file not found: {s}\n"
                            f"cwd={Path.cwd()}\n"
                            f"tried: {p.resolve()} and {maybe}")

def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    log.info(f"loading seed: {seed_path}")
    return _read_json_bom_tolerant(seed_path)

def run(seed: Path) -> None:
    seeds = load_seed(seed)
    docs: List[Dict[str, Any]] = []
    crawled_at = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    for s in seeds:
        typ = (s.get("type") or "").lower()
        url = s["url"]
        lang = s.get("lang", "ja")

        if typ == "pdf":
            text = extract_from_pdf(url)
            title = s.get("title") or "出典"
        else:
            title, text = extract_from_html(url)

        doc_id = sha(url)
        docs.append({
            "id": doc_id,
            "text": (text or "")[:10000],
            "meta": {
                "url": url,
                "title": title,
                "published_at": s.get("published_at"),
                "crawled_at": crawled_at,
                "lang": lang,
            }
        })

    if not docs:
        log.warning("no documents to upsert")
        return

    upsert(docs)
    log.info(f"ingested: {len(docs)}")

# ------- CLI -------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="gov-docs ingest")
    parser.add_argument("--seed", help="path to seed_urls.json (UTF-8 BOM/NoBOM both OK)", default=None)
    args = parser.parse_args()

    seed_path = _resolve_seed_path(args.seed)
    run(seed_path)
