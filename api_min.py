# api_min.py
import json, os, re
from typing import List, Dict
from fastapi import FastAPI
from uvicorn import run

BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, "data", "db", "texts.json")

app = FastAPI(title="qa_service_min", version="1.0.0")

def load_texts():
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            items = json.load(f)
            if isinstance(items, list):
                return items
    except Exception:
        pass
    return []

DOCS: List[Dict] = load_texts()

def tokenize(s: str):
    return set(re.findall(r"\w+", (s or "").lower()))

def score(q: str, doc: Dict) -> float:
    tq = tokenize(q)
    td = tokenize(f"{doc.get('title','')} {doc.get('text','')}")
    if not tq or not td:
        return 0.0
    inter = len(tq & td)
    return inter / len(tq)  # クエリ被覆率（簡易スコア）

@app.get("/__version")
def version():
    return "qa_service_min 1.0.0"

@app.get("/health")
def health():
    return {"ok": True, "index_exists": True, "texts_exists": bool(DOCS), "min_score": 0.0, "top_k_default": 5}

@app.get("/reload")
@app.post("/reload")
def reload():
    global DOCS
    DOCS = load_texts()
    return {"ok": True, "count": len(DOCS)}

@app.get("/search")
def search(q: str, top_k: int = 5, min_score: float = 0.0):
    scored = []
    for d in DOCS:
        s = score(q, d)
        if s >= min_score:
            scored.append((s, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [{
        "id": d.get("id"),
        "title": d.get("title"),
        "score": float(s),
        "snippet": (d.get("text") or "")[:160],
        "source_url": d.get("source_url"),
        "source_path": d.get("source_path"),
    } for s, d in scored[:top_k]]
    return {"ok": True, "query": q, "count": len(results), "results": results}

if __name__ == "__main__":
    run("api_min:app", host="127.0.0.1", port=8010, reload=True)
