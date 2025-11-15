# v2/pipelines/ingest.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import codecs

DEFAULT_SEED = Path(__file__).parent / "config" / "seed_urls.json"


def _read_json_tolerant(path: Path) -> Any:
    """
    UTF-8 / UTF-8-sig(BOM) の両方を許容して JSON を読み込む。
    先頭に BOM があれば取り除いてからデコードする。
    """
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        data = data[len(codecs.BOM_UTF8):]
    # まず utf-8 を試し、ダメなら utf-8-sig でもう一度
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return json.loads(data.decode("utf-8-sig"))


def _normalize_seeds(obj: Any) -> List[Dict[str, Any]]:
    """
    seed が配列でも単一オブジェクトでも受け付ける。
    """
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    raise ValueError("seed file must be a JSON array or object")


def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    if not seed_path.exists():
        raise FileNotFoundError(f"seed file not found: {seed_path}")
    payload = _read_json_tolerant(seed_path)
    seeds = _normalize_seeds(payload)
    return seeds


def run(seed: Path) -> None:
    seeds = load_seed(seed)
    print(f"[ingest] loaded {len(seeds)} seed(s) from: {seed.resolve()}")

    # TODO: ここで実際の抽出・埋め込み・upsert を呼ぶ
    # 例：
    # from app.store.vector import upsert
    # from pipelines.extract import fetch_and_parse
    # for s in seeds:
    #     docs = fetch_and_parse(s)
    #     upsert(docs)

    # ひとまず動作確認用に内容を出力
    for i, s in enumerate(seeds, 1):
        title = s.get("title", "(no title)")
        url = s.get("url", "(no url)")
        print(f"  - [{i}] {title} <{url}>")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest pipeline (BOM tolerant)")
    parser.add_argument(
        "--seed",
        type=str,
        default=str(DEFAULT_SEED),
        help="Path to seed_urls.json (relative or absolute)."
    )
    args = parser.parse_args(argv)

    seed_path = Path(args.seed)
    if not seed_path.is_absolute():
        # 実行ディレクトリからの相対パスもサポート
        seed_path = Path.cwd() / seed_path

    try:
        run(seed_path)
        return 0
    except Exception as e:
        print(f"[ingest] ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
