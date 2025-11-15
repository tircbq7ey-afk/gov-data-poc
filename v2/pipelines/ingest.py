# v2/pipelines/ingest.py

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import codecs


# --- 既存プロジェクト依存（無くても ingest 自体は動くようにする） ---
def _try_imports() -> None:
    try:
        # 例：ベクタ格納など（実際の実装がまだでもここは OK）
        from app.store.vector import upsert  # noqa: F401
    except Exception:
        # まだ実装していない／ローカルに無い環境でもスルー
        pass


# --- UTF-8 (BOM あり/なし両方) を安全に読むユーティリティ ---
def read_json(path: Path):
    # codec を使って、BOM があってもなくても確実に吸収する
    with open(path, "rb") as f:
        raw = f.read()

    if raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8) :]

    text = raw.decode("utf-8")
    return json.loads(text)


def default_seed_path() -> Path:
    """
    デフォルトの seed ファイルパス:
    このファイル (ingest.py) の隣に config/seed_urls.json がある想定。
    """
    here = Path(__file__).resolve()
    return (here.parent / "config" / "seed_urls.json").resolve()


def load_seed(seed_path: str | None) -> list[dict]:
    """
    seed_urls.json を読み込み、list[dict] を返す。
    - 相対パスでも OK（カレントディレクトリから解決）
    - dict 形式でも、よくあるキー名から list を取り出す
    """
    p = Path(seed_path).expanduser() if seed_path else default_seed_path()

    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()

    if not p.exists():
        raise FileNotFoundError(f"seed file not found: {p}")

    data = read_json(p)

    if isinstance(data, dict):
        # {"seeds":[...]} / {"items":[...]} / {"data":[...]} のどれかを想定
        data = data.get("seeds") or data.get("items") or data.get("data") or []

    if not isinstance(data, list):
        raise ValueError("seed file must be a list[dict]")

    return data


def run(seed_path: str | None) -> None:
    """
    メイン処理。
    ここではとりあえず件数を表示するだけにしておき、
    実際のクロール・埋め込み処理はこの中で呼び出す想定。
    """
    _try_imports()
    seeds = load_seed(seed_path)

    # TODO: ここで実際のクロール・ベクタ登録処理に seeds を渡す
    print(f"[ingest] {len(seeds)} items loaded from seed file")


def cli(argv=None) -> None:
    parser = argparse.ArgumentParser(description="VisaNavi ingest")
    parser.add_argument(
        "--seed",
        dest="seed",
        help="path to seed_urls.json (UTF-8 / UTF-8 with BOM both ok)",
    )
    args = parser.parse_args(argv)
    run(args.seed)


if __name__ == "__main__":
    cli(sys.argv[1:])
