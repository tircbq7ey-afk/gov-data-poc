from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from . import extract
from app.store import vector


def _resolve_seed_path(seed_arg: str) -> Path:
    """
    Resolve --seed path robustly.

    Accepts:
      - absolute path
      - relative to current working directory
      - project-root relative paths such as "v2/pipelines/config/seed_urls.json"
      - Windows style backslashes
    """
    cand = Path(seed_arg).expanduser()
    if cand.is_absolute() and cand.exists():
        return cand

    # try relative to CWD
    cand2 = (Path.cwd() / cand).resolve()
    if cand2.exists():
        return cand2

    # try project root (two parents up from this file: v2/pipelines/ingest.py -> repo root)
    project_root = Path(__file__).resolve().parents[2]
    cand3 = (project_root / cand).resolve()
    if cand3.exists():
        return cand3

    # as a last resort, try removing leading "v2/" if present
    if str(cand).startswith(("v2/", "v2\\")):
        cand4 = (project_root / str(cand).split("\\", 1)[-1].split("/", 1)[-1]).resolve()
        if cand4.exists():
            return cand4

    raise FileNotFoundError(f"seed file not found: {seed_arg}")


def load_seed(path: Path) -> List[Dict]:
    """
    Load seed_urls.json and normalize items.

    - Reads with encoding='utf-8-sig' to tolerate UTF-8 BOM (Windows PowerShell writes BOM by default).
    - Validates minimal required fields.
    """
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    norm: List[Dict] = []
    for it in data:
        url = (it or {}).get("url", "").strip()
        if not url:
            continue
        norm.append(
            {
                "url": url,
                "type": it.get("type", "html"),
                "title": it.get("title", ""),
                "published_at": it.get("published_at", ""),
                "lang": it.get("lang", "ja"),
            }
        )
    if not norm:
        raise ValueError("seed list is empty after normalization")
    return norm


def run(seed_file: Path) -> None:
    seeds = load_seed(seed_file)
    total_chunks = 0
    for s in seeds:
        docs = extract.build_docs(s)
        total_chunks += vector.upsert(docs)
    print(f"ingest done: {len(seeds)} seeds, {total_chunks} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG ingest pipeline")
    parser.add_argument("--seed", required=True, help="path to seed_urls.json")
    args = parser.parse_args()
    seed_path = _resolve_seed_path(args.seed)
    run(seed_path)


if __name__ == "__main__":
    main()
