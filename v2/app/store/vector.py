# -*- coding: utf-8 -*-
import os
import chromadb
from chromadb.utils import embedding_functions

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
os.makedirs(CHROMA_DIR, exist_ok=True)

MODEL_NAME = "all-MiniLM-L6-v2"
_embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_NAME
)

_client = chromadb.PersistentClient(path=CHROMA_DIR)
_COLLECTION = _client.get_or_create_collection(
    name="gov-v2",
    embedding_function=_embedder,
    metadata={"hnsw:space": "cosine"},
)

def search(query: str, k: int = 5):
    if not query:
        return [], []
    res = _COLLECTION.query(query_texts=[query], n_results=max(1, k))
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return docs, metas
