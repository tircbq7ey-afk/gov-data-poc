import os
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma")
EMBEDDER = os.getenv("EMBEDDER", "sbert")  # "sbert" | "openai"
def _ef():
    if EMBEDDER == "openai":
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"), model_name="text-embedding-3-small"
        )
    else:
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
_client = PersistentClient(path=CHROMA_DIR)
_collection = _client.get_or_create_collection(name="govdocs", embedding_function=_ef())
def upsert(docs):
    _collection.upsert(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[d["meta"] for d in docs],
    )
def search(query, k=5):
    res = _collection.query(query_texts=[query], n_results=k)
    items = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i] or {}
        items.append({
            "text": res["documents"][0][i],
            "score": float(res.get("distances", [[0]])[0][i]) if "distances" in res else 0.0,
            "meta": meta
        })
    return items
