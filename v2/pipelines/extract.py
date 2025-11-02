from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import hashlib
import re
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fetch_text(seed: Dict) -> str:
    url = seed["url"]
    typ = seed.get("type", "html")
    if typ == "pdf":
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        doc = fitz.open(stream=r.content, filetype="pdf")
        pages = []
        for p in doc:
            pages.append(p.get_text("text"))
        return _clean("\n".join(pages))
    else:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # main 内テキスト優先、fallback は全体
        main = soup.find("main")
        text = (main.get_text(" ") if main else soup.get_text(" "))
        return _clean(text)

def chunk(text: str, size: int = 800, overlap: int = 120) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - overlap
    return chunks

def build_docs(seed: Dict) -> List[Dict]:
    raw = fetch_text(seed)
    chs = chunk(raw)
    docs: List[Dict] = []
    base_id = _hash(seed["url"])
    for i, t in enumerate(chs):
        docs.append({
            "id": f"{base_id}:{i}",
            "text": t,
            "metadata": {
                "url": seed["url"],
                "title": seed.get("title", ""),
                "type": seed.get("type", "html"),
                "lang": seed.get("lang", "ja"),
                "chunk_index": i,
            }
        })
    return docs
