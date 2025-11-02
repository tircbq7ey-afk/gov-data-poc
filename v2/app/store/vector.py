from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# 永続ディレクトリ: repo_root/data/chroma
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "chroma"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_client = chromadb.PersistentClient(
    path=str(DATA_DIR),
    settings=Settings(allow_reset=False)
)
_collection = _client.get_or_create_collection(name="gov-docs")
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

def _embed(texts: List[str]) -> List[List[float]]:
    # 正規化つきで安定化
    return _embedder.encode(texts, normalize_embeddings=True).tolist()

def upsert(docs: List[Dict[str, Any]]) -> int:
    if not docs:
        return 0
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metas = [d["metadata"] for d in docs]
    _collection.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=_embed(texts))
    return len(docs)

def query(q: str, k: int = 5) -> List[Dict[str, Any]]:
    res = _collection.query(
        query_embeddings=_embed([q]),
        n_results=max(1, min(k, 20)),
        include=["metadatas", "documents", "distances"],
    )
    out: List[Dict[str, Any]] = []
    if not res or not res.get("documents"):
        return out
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    for text, meta, dist in zip(docs, metas, dists):
        out.append({
            "text": text,
            "score": float(1.0 - dist),  # 近いほど高スコアに
            "url": meta.get("url"),
            "title": meta.get("title"),
            "chunk_index": meta.get("chunk_index"),
            "type": meta.get("type"),
            "lang": meta.get("lang"),
        })
    return out
