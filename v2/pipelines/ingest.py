# v2/pipelines/ingest.py
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# （あなたの既存コードに合わせて必要ならコメントアウトを外してください）
# from app.store.vector import upsert  # 既存のベクター登録関数
# from pipelines.extract import fetch_and_extract  # 既存の抽出処理などがあれば

LOG = logging.getLogger("ingest")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

# デフォルトの seed ファイル（このファイルと同じディレクトリの config/seed_urls.json）
DEFAULT_SEED = Path(__file__).resolve().parent / "config" / "seed_urls.json"


def _load_json_tolerant(path: Path) -> Any:
    """
    UTF-8 / UTF-8-SIG(BOM付) の両方に耐性を持って JSON を読み込む。
    - Windows/PowerShell で BOM 付きになっても落とさない。
    """
    # まずバイナリで読んで BOM を吸収
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8")  # BOM 無し想定
    except UnicodeDecodeError:
        # BOM 付き（utf-8-sig）で再解釈
        txt = raw.decode("utf-8-sig")
    return json.loads(txt)


def load_seed(seed_path: Path) -> List[Dict[str, Any]]:
    if not seed_path.exists():
        raise FileNotFoundError(f"seed file not found: {seed_path}")
    data = _load_json_tolerant(seed_path)
    if not isinstance(data, list):
        raise ValueError("seed must be a JSON array of objects")
    # フィールド名のゆらぎや欠損に軽いバリデーションを入れておく
    normed: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            LOG.warning("seed[%d] is not an object: %r", i, item)
            continue
        url = item.get("url")
        typ = item.get("type")
        if not url or not typ:
            LOG.warning("seed[%d] missing required fields: %r", i, item)
            continue
        normed.append(item)
    return normed


def run(seed_file: Path) -> None:
    LOG.info("seed file: %s", seed_file)
    seeds = load_seed(seed_file)
    LOG.info("loaded %d seeds", len(seeds))

    # --- ここから先はあなたの既存処理に接続してください ---
    # 例：
    # for s in seeds:
    #     doc = fetch_and_extract(s["url"], doc_type=s["type"], lang=s.get("lang", "ja"))
    #     upsert(doc)  # ベクターDBへ登録
    # ---------------------------------------------------------

    # とりあえず動作確認としてURL一覧をログに出す
    for s in seeds:
        LOG.info("seed: type=%s url=%s", s.get("type"), s.get("url"))

    LOG.info("ingest finished.")


def main():
    parser = argparse.ArgumentParser(description="Seeded ingest runner")
    parser.add_argument(
        "--seed",
        type=str,
        default=str(DEFAULT_SEED),
        help="Path to seed_urls.json (default: v2/pipelines/config/seed_urls.json)",
    )
    args = parser.parse_args()

    # 渡されたパスは実行ディレクトリに依存しないよう絶対パス化
    seed_path = Path(args.seed).expanduser()
    if not seed_path.is_absolute():
        # 相対パスは「現在の作業ディレクトリ」基準で解決
        seed_path = (Path.cwd() / seed_path).resolve()

    run(seed_path)


if __name__ == "__main__":
    main()
