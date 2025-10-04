# build_bm25.py
from pathlib import Path
import pickle, json
from rank_bm25 import BM25Okapi

DB = Path("data/db")
PKL = DB / "bm25.pkl"
IDX = DB / "bm25.index"
META = DB / "bm25_meta.json"

def main():
    d = pickle.loads(PKL.read_bytes())
    corpus = d["corpus"]; ids = d["ids"]
    bm25 = BM25Okapi(corpus)
    with open(IDX, "wb") as f:
        pickle.dump({"bm25": bm25, "ids": ids}, f, protocol=pickle.HIGHEST_PROTOCOL)
    META.write_text(json.dumps({"count": len(ids)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(ids)} docs -> {IDX.name}")

if __name__ == "__main__":
    main()
