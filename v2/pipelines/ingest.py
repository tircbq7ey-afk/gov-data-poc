# v2/pipelines/ingest.py  完全版
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

# ---- seed の読み込み ---------------------------------------------------------
def load_seed(path: Path) -> List[Dict[str, Any]]:
    """
    seed_urls.json を読み込み、list[dict] を返す。
    - UTF-8 / UTF-8-SIG（BOM付き）どちらでもOK
    - JSON 配列を想定
    """
    if not path.exists():
        raise FileNotFoundError(f"seed file not found: {path}")

    # BOM を許容
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # 失敗したとき、先頭数十文字を一緒に表示して原因特定しやすく
        head = text[:120].replace("\n", "\\n")
        raise ValueError(f"invalid JSON in seed file: {path} (head={head!r})") from e

    if not isinstance(data, list):
        raise TypeError(f"seed must be a JSON array, got {type(data).__name__}")

    # 必須キーの軽いチェック
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "url" not in item:
            raise ValueError(f"seed[{i}] must be an object with 'url' key, got: {item!r}")
        # 補完（欠けていたら埋める）
        item.setdefault("type", "html")
        item.setdefault("title", "")
        item.setdefault("published_at", "")
        item.setdefault("lang", "ja")
    return data

# ---- ダミー実装（ここに将来のクロール/埋め込み処理を載せる） -------------------
def run(seed_path: Path) -> None:
    seeds = load_seed(seed_path)
    # とりあえず件数だけ表示
    print(f"[ingest] loaded {len(seeds)} seeds from {seed_path}")
    for s in seeds:
        print(f" - {s['type']:4} | {s['url']}")

# ---- CLI ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest pipeline (v2)")
    p.add_argument(
        "--seed",
        type=Path,
        required=True,
        help="path to seed_urls.json (e.g. v2/pipelines/config/seed_urls.json)",
    )
    return p.parse_args()

def main() -> None:
    args = parse_args()
    run(args.seed.resolve())

if __name__ == "__main__":
    main()
