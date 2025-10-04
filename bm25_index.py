# bm25_index.py
import json, re, pickle
from pathlib import Path
from typing import List, Dict, Tuple

DB = Path("data/db")
TEXTS = DB / "texts.json"
BM25_PKL = DB / "bm25.pkl"
BM25_META = DB / "bm25_meta.json"

JA_RE = re.compile(r"[ぁ-んァ-ン一-龥]+")

def ja_bigrams(s: str) -> List[str]:
    return [s[i:i+2] for i in range(len(s)-1)] if len(s) >= 2 else ([s] if s else [])

def tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    toks: List[str] = []
    pos = 0
    for m in JA_RE.finditer(text):
        chunk = text[pos:m.start()]
        toks += re.findall(r"[a-z0-9]+", chunk)
        toks += ja_bigrams(m.group())
        pos = m.end()
    toks += re.findall(r"[a-z0-9]+", text[pos:])
    return toks

def load_texts() -> List[Dict]:
    data = json.loads(TEXTS.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = [data]
    return [r for r in data if r.get("id") and (r.get("title") or r.get("text"))]

def build_corpus() -> Tuple[List[List[str]], List[str]]:
    rows = load_texts()
    ids, corpus = [], []
    for r in rows:
        ids.append(str(r["id"]))
        blob = (r.get("title", "") + "\n" + r.get("text", "")).strip()
        corpus.append(tokenize(blob))
    return corpus, ids

def main():
    DB.mkdir(parents=True, exist_ok=True)
    corpus, ids = build_corpus()
    with open(BM25_PKL, "wb") as f:
        pickle.dump({"corpus": corpus, "ids": ids}, f, protocol=pickle.HIGHEST_PROTOCOL)
    BM25_META.write_text(json.dumps({"count": len(ids)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(ids)} docs -> {BM25_PKL.name}, {BM25_META.name}")

if __name__ == "__main__":
    main()
