# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import faiss

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data" / "db"
INDEX = DB_DIR / "faiss.index"
TEXTS = DB_DIR / "texts.json"

def count_lines(p: Path) -> int:
    if not p.exists(): return 0
    c = 0
    with p.open("r", encoding="utf-8") as f:
        for _ in f: c += 1
    return c

def main():
    print("TEXTS path :", TEXTS)
    print("INDEX path :", INDEX)
    if not TEXTS.exists() or not INDEX.exists():
        print("exists:", TEXTS.exists(), INDEX.exists())
        print("MATCH (ntotal==records):", False)
        return
    total = count_lines(TEXTS)
    idx = faiss.read_index(str(INDEX))
    print("texts records=", total)
    print(f"faiss: ntotal={idx.ntotal} dim={idx.d} type={type(idx).__name__}")
    print("MATCH (ntotal==records):", idx.ntotal == total)

if __name__ == "__main__":
    main()
