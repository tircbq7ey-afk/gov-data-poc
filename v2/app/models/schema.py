from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
class SearchRequest(BaseModel):
    query: str
    lang: str = Field(default="ja")
class Citation(BaseModel):
    url: HttpUrl
    title: str
    published_at: Optional[str] = None
    crawled_at: Optional[str] = None
class SearchResponse(BaseModel):
    answer: str
    citations: List[Citation]
    score: float

class FeedbackRequest(BaseModel):
    query: str
    answer: str
    type: str  # "flag" | "like" | "dislike" | "wrong" | "other"
    note: Optional[str] = None
