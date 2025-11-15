# pipelines/ingest.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Dict

# ---- 設定 -------------------------------------------------------------

# デフォルトのseedファイル（このファイル = pipelines/ の直下基準）
DEFAULT_SEED = Path(__file__).resolve().parent / "config" / "seed_urls.json"

# ---- ユーティリティ ----------------------------------------------------

def resolve_seed_path(seed_arg: str | None) -> Path:
    """
    seed引数があれば最優先で解決。相対/絶対/スラ/バックスラ どれでもOK。
    見つからない場合は pipelines/config/seed_urls.json を使う。
    """
    if seed_arg:
        # \ / の混在を許し、~ 展開も許す
        cand = Path(seed_arg.replace("\\", "/")).expanduser()
        if cand.is_file():
            return cand.resolve()

        # CWD相対 → 失敗したら pipelines/ 相対も試す
        cwd = Path.cwd()
        if (cwd / cand).is_file():
            return (cwd / cand).resolve()

        base = Path(__file__).resolve().parent
        if (base / cand).is_file():
            return (base / cand).resolve()

    return DEFAULT_SEED


def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    """
    JSONをUTF-8（BOM付きも可）で読み込む。
    Windows PowerShell 5.1の `Set-Content -Encoding utf8` はBOM付きになるため
    ここでutf-8-sigで安全に吸収する。
    """
    if not seed_path.is_file():
        raise FileNotFoundError(f"seed file not found: {seed_path}")

    # ★ ここが恒久対策：utf-8-sig でBOMを許容
    with seed_path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("seed must be a list of objects")

    # 最低限の正規化（keyの存在チェックなど必要に応じて）
    norm: List[Dict[str, Any]] = []
    for i, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise ValueError(f"seed item #{i} is not an object")
        # 必須候補: url / type
        url = row.get("url")
        typ = row.get("type", "")
        if not url:
            raise ValueError(f"seed item #{i} missing 'url'")
        norm.append({
            "url": url,
            "type": typ,
            "title": row.get("title", ""),
            "lang": row.get("lang", ""),
            "published_at": row.get("published_at", ""),
        })
    return norm


# ---- メイン処理（必要最低限のダミー実装） ------------------------------

def run(seed_path: Path) -> None:
    seeds = load_seed(seed_path)
    # ここで本来のインジェスト処理を呼ぶ。
    # 取り急ぎ、読み込めたことが分かるようログだけ出す。
    print(f"[ingest] loaded {len(seeds)} seeds from {seed_path}")
    for i, s in enumerate(seeds, 1):
        print(f"  {i:02d}: {s['type']:>4}  {s['url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="GovDocs ingest")
    ap.add_argument(
        "--seed",
        help="Path to seed_urls.json (relative/absolute OK). "
             "If omitted, use pipelines/config/seed_urls.json",
        default=None,
    )
    args = ap.parse_args()

    seed_path = resolve_seed_path(args.seed)
    run(seed_path)


if __name__ == "__main__":
    main()
