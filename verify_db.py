# verify_db.py
from pathlib import Path
import json, faiss

DATA = Path("data/db")
T = DATA / "texts.json"
I = DATA / "faiss.index"

def main():
    if not T.exists():
        print(f"TEXTS path : {T} (not found)"); return
    if not I.exists():
        print(f"INDEX path : {I} (not found)")
    texts = json.loads(T.read_text(encoding="utf-8-sig"))
    print(f"TEXTS path : {T}")
    print(f"INDEX path : {I}")
    print(f"texts records: {len(texts)}")
    if I.exists():
        index = faiss.read_index(str(I))
        print(f"faiss: ntotal={index.ntotal} dim={index.d} type={type(index).__name__}")
        print("MATCH (ntotal==records):", index.ntotal == len(texts))
    else:
        print("MATCH (ntotal==records): False")

if __name__ == "__main__":
    main()
