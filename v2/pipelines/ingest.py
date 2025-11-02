# v2/pipelines/ingest.py
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import List

# ---- 型定義 ---------------------------------------------------------------
@dataclass
class Seed:
    url: str
    type: str = "html"   # "pdf" or "html"
    title: str = ""
    published_at: str = ""
    lang: str = "ja"

# ---- ユーティリティ --------------------------------------------------------
def load_seed(path: str) -> List[Seed]:
    """
    JSON を UTF-8(BOMあり/なし両対応)で読み込み、Seed配列を返す。
    """
    # まずは 'utf-8-sig'（BOMを自動で無視）で開く
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("seed file must be a JSON array")

    seeds: List[Seed] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"seed[{i}] is not an object")
        url = item.get("url", "").strip()
        if not url:
            continue
        seeds.append(
            Seed(
                url=url,
                type=item.get("type", "html"),
                title=item.get("title", "") or "",
                published_at=item.get("published_at", "") or "",
                lang=item.get("lang", "ja") or "ja",
            )
        )
    return seeds

def ensure_project_root() -> str:
    """
    v2/ 配下から実行されてもパスがブレないように、プロジェクト直下を返す。
    （このファイルが v2/pipelines/ingest.py にある前提）
    """
    here = os.path.abspath(os.path.dirname(__file__))  # .../v2/pipelines
    v2_dir = os.path.dirname(here)                      # .../v2
    return v2_dir

# ---- ダミー upsert（ベクトルDBが未接続でも通す） ---------------------------
def upsert_dummy(seeds: List[Seed]) -> None:
    # ここは後で実DBに差し替えればOK。今は確認用にログだけ出す。
    print(f"[ingest] {len(seeds)} seeds loaded")
    for s in seeds:
        print(f"  - ({s.type}) {s.url}")

# ---- メイン ---------------------------------------------------------------
def main():
    project_root = ensure_project_root()
    default_seed = os.path.join(project_root, "pipelines", "config", "seed_urls.json")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        default=default_seed,
        help=f"seed json path (default: {default_seed})"
    )
    args = parser.parse_args()

    path = os.path.abspath(args.seed)
    if not os.path.exists(path):
        raise FileNotFoundError(f"seed file not found: {path}")

    seeds = load_seed(path)
    upsert_dummy(seeds)

if __name__ == "__main__":
    main()
