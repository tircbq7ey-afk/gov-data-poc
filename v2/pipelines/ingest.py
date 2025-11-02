# -*- coding: utf-8 -*-
"""
Seed URL から本文を取り出し、Chroma に埋め込んで保存する簡易インジェスト
- HTML: requests + BeautifulSoup
- PDF : PyMuPDF
- 埋め込み: sentence-transformers 'all-MiniLM-L6-v2'
- ストア: Chroma (ローカル)
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Dict

import requests
from bs4 import BeautifulSoup

import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
os.makedirs(CHROMA_DIR, exist_ok=True)

MODEL_NAME = "all-MiniLM-L6-v2"
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_NAME
)

client = chromadb.PersistentClient(path=CHROMA_DIR)
COLLECTION_NAME = "gov-v2"
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedder,
    metadata={"hnsw:space": "cosine"},
)

@dataclass
class Seed:
    url: str
    type: str  # "html" or "pdf"
    title: str = ""
    lang: str = "ja"
    published_at: str = ""

def _load_json_any(path: str) -> List[Dict]:
    # BOM あり/なしをどちらも許容
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(raw.decode("utf-8-sig"))

def load_seed(path: str) -> List[Seed]:
    items = _load_json_any(path)
    seeds: List[Seed] = []
    for it in items:
        if not it.get("url"):
            continue
        seeds.append(
            Seed(
                url=it["url"],
                type=(it.get("type") or "html").lower(),
                title=it.get("title", ""),
                lang=it.get("lang", "ja"),
                published_at=it.get("published_at", ""),
            )
        )
    return seeds

def clean_text(txt: str) -> str:
    txt = re.sub(r"\r?\n+", "\n", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt.strip()

def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # 文量を優先して可視テキストを取得
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    text = soup.get_text(separator="\n")
    return clean_text(text)

def fetch_pdf(url: str) -> str:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        pages = [p.get_text("text") for p in doc]
    return clean_text("\n".join(pages))

def chunk(text: str, size: int = 800, overlap: int = 100) -> Iterable[str]:
    if not text:
        return []
    tokens = text.split("\n")
    cur: List[str] = []
    total = 0
    for line in tokens:
        cur.append(line)
        total += len(line)
        if total >= size:
            yield clean_text("\n".join(cur))
            # overlap 分だけ残して次へ
            keep = clean_text("\n".join(cur))[-overlap:]
            cur = [keep] if keep else []
            total = len(keep)
    if cur:
        yield clean_text("\n".join(cur))

def upsert(url: str, title: str, chunks: List[str]):
    if not chunks:
        return
    ids = [f"{url}#chunk-{i}" for i in range(len(chunks))]
    metas = [{"url": url, "title": title, "chunk_index": i} for i in range(len(chunks))]
    collection.upsert(documents=chunks, ids=ids, metadatas=metas)

def run(seed_path: str):
    seeds = load_seed(seed_path)
    for s in seeds:
        print(f"[INGEST] {s.type} -> {s.url}")
        try:
            if s.type == "pdf":
                text = fetch_pdf(s.url)
            else:
                text = fetch_html(s.url)
            parts = list(chunk(text))
            upsert(s.url, s.title or s.url, parts)
            print(f"  OK: {len(parts)} chunks")
        except Exception as e:
            print(f"  FAIL: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, help="path to seed_urls.json")
    args = parser.parse_args()

    run(args.seed)
