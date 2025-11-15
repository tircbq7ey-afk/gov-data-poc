# v2/pipelines/ingest.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

# --- 既存プロジェクト依存（存在しない環境でも動くように遅延 import）
def _try_imports():
    try:
        # 例: ベクタ格納など（無い環境でも ingest 自体は動作させたい）
        from app.store.vector import upsert  # noqa: F401
    except Exception:
        pass

# --- UTF-8(BOM/無BOM) で JSON を安全に読む
def read_json(path: Path):
    # utf-8-sig で BOM を自動吸収
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def default_seed_path() -> Path:
    # このファイルの隣の config/seed_urls.json を既定に
    here = Path(__file__).resolve()
    return (here.parent / "config" / "seed_urls.json").resolve()

def load_seed(seed_path: str | None) -> list[dict]:
    p = Path(seed_path).expanduser() if seed_path else default_seed_path()
    if not p.is_absolute():
        # 実行場所に依存せず、プロジェクト root / v2 からの相対も解決
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise FileNotFoundError(f"seed file not found: {p}")
    data = read_json(p)
    if isinstance(data, dict):  # 配列でない形式にも耐性
        data = (data.get("seeds") or data.get("items") or data.get("data") or [])
    if not isinstance(data, list):
        raise ValueError("seed file must be a list[dict]")
    return data

def run(seed_path: str | None):
    _try_imports()
    seeds = load_seed(seed_path)
    # ここで実際の処理（クロール・埋め込み等）に渡す
    # 既存実装があれば差し替えてください。ひとまず可視化のみ。
    print(f"[ingest] {len(seeds)} items loaded")

def cli(argv=None):
    ap = argparse.ArgumentParser(description="VisaNavi ingest")
    ap.add_argument("--seed", dest="seed", help="path to seed_urls.json (UTF-8/BOM both ok)")
    args = ap.parse_args(argv)
    run(args.seed)

if __name__ == "__main__":
    cli(sys.argv[1:])
