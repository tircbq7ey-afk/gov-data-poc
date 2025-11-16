import logging
from typing import Dict, Any
from app.store.vector import get_vector_store

logger = logging.getLogger(__name__)

def handle(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search handler.
    Expected request body:
      {
        "query": "在留カード 住所 変更",
        "k": 5
      }
    """

    try:
        query: str = req.get("query", "")
        k: int = req.get("k", 5)

        if not query:
            return {"error": "query is required"}

        collection = get_vector_store()

        # NOTE: Chroma の検索は search ではなく query
        results = collection.query(
            query_texts=[query],
            n_results=k
        )

        # Chroma のレスポンス形式に合わせて整形
        output = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for doc_id, doc, dist, meta in zip(ids, docs, distances, metadatas):
            output.append({
                "id": doc_id,
                "text": doc,
                "distance": dist,
                "metadata": meta
            })

        return {"results": output}

    except Exception as e:
        logger.exception("Search failed")
        return {"error": str(e)}
