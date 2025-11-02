from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.store import vector

router = APIRouter()

class QueryReq(BaseModel):
    query: str = Field(..., description="ユーザー質問")
    k: int = Field(5, ge=1, le=20, description="取得件数")

@router.get("/health")
def health():
    return {"status": "ok", "p95_ms": 0.0}

@router.post("/search")
def search(req: QueryReq):
    hits = vector.query(req.query, k=req.k)
    if not hits:
        return {"answer": "", "citations": [], "score": 0.0}
    top = hits[0]
    citations = [{
        "url": h["url"],
        "title": h["title"],
        "chunk_index": h["chunk_index"]
    } for h in hits]
    return {"answer": top["text"], "citations": citations, "score": top["score"]}
