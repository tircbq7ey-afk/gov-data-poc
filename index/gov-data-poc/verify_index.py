# -*- coding: utf-8 -*-
import json, faiss, pathlib, sys

DB_DIR = pathlib.Path("data/db")
INDEX_PATH = DB_DIR / "faiss.index"
TEXTS_PATH = DB_DIR / "texts.json"

def load_texts_ndjson(path: pathlib.Path):
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            items.append(json.loads(s))
    return items

def main():
    if not INDEX_PATH.exists():
        print(f"[error] index not found: {INDEX_PATH}")
        sys.exit(1)
    if not TEXTS_PATH.exists():
        print(f"[error] texts not found: {TEXTS_PATH}")
        sys.exit(1)

    index = faiss.read_index(str(INDEX_PATH))
    nvec = index.ntotal
    texts = load_texts_ndjson(TEXTS_PATH)
    nmeta = len(texts)

    print(f"[ok] vectors in index : {nvec}")
    print(f"[ok] rows in texts    : {nmeta}")
    print("[ok] MATCH" if nvec == nmeta else "[warn] MISMATCH")

if __name__ == "__main__":
    main()
