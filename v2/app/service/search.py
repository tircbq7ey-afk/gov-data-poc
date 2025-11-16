# app/service/search.py

from fastapi import APIRouter

from ..models.schema import SearchRequest, SearchResponse
from ..store.vector import search_documents

# /search 配下のAPIをまとめるルーター
router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    """
    ベクターストアからクエリ検索して結果を返すエンドポイント
    """
    results = search_documents(req.query, k=req.k)

    return SearchResponse(
        query=req.query,
        results=results,
    )
