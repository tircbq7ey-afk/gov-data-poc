# v2/app/service/search.py
from typing import Any, Dict, List

from app.store.vector import get_vector_store


def handle(req) -> Dict[str, Any]:
    """
    検索 API のビジネスロジック。
    例外が出ても 500 にはせず、{"error": "..."} を返します。
    """
    # FastAPI のモデル/SearchRequest でも、生の dict でも動くようにしておく
    try:
        query = req.query if hasattr(req, "query") else req["query"]
        k = req.k if hasattr(req, "k") else req.get("k", 5)
    except Exception as e:
        return {"error": f"invalid request: {e}"}

    try:
        collection = get_vector_store()

        result = collection.query(
            query_texts=[query],
            n_results=int(k),
            include=["documents", "metadatas", "distances", "ids"],
        )

        docs: List[str] = (result.get("documents") or [[]])[0]
        metadatas: List[Dict[str, Any]] = (result.get("metadatas") or [[]])[0]
        ids: List[str] = (result.get("ids") or [[]])[0]
        scores: List[float] = (result.get("distances") or [[]])[0]

        items: List[Dict[str, Any]] = []
        for doc, meta, _id, score in zip(docs, metadatas, ids, scores):
            source_url = None
            title = None
            if isinstance(meta, dict):
                source_url = meta.get("url") or meta.get("source_url")
                title = meta.get("title")

            items.append(
                {
                    "id": _id,
                    "title": title,
                    "source_url": source_url,
                    "text": doc,
                    "score": float(score) if score is not None else None,
                }
            )

        return {"results": items}

    except Exception as e:
        # ここで print しておくと、ターミナルに詳細が出ます
        print("Search error:", repr(e))
        return {"error": str(e)}
