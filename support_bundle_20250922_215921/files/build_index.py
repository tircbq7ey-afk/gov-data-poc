# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
from typing import List, Dict

import numpy as np

# faiss は pip で入れてある前提
import faiss


# ---------- 設定の読み込み ----------
ROOT = Path(__file__).resolve().parent
CFG_PATH = ROOT / "settings.json"

with CFG_PATH.open(encoding="utf-8") as f:
    CFG = json.load(f)

# paths
P = CFG["paths"]
DB_DIR     = ROOT / P["db_dir"]
TEXTS_JSON = ROOT / P["texts_json"]
FAISS_IDX  = ROOT / P["faiss_index"]
ID_MAP     = ROOT / P["id_map"]
DOC_MAP    = ROOT / P["doc_map"]
META_JSON  = ROOT / P["meta"]

DB_DIR.mkdir(parents=True, exist_ok=True)

# 埋め込み設定（環境変数があれば優先）
EMBED_BACKEND = os.getenv("EMBED_BACKEND", CFG.get("embed_backend", "openai")).lower()
EMBED_MODEL   = os.getenv("EMBED_MODEL",   CFG.get("embed_model"))
EMBED_DIM     = int(os.getenv("EMBED_DIM", str(CFG.get("embed_dim", 1536))))


def load_texts(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"texts.json がありません: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    # 期待形式: [{"id": "...", "text": "...", "url": "..."}]
    return data


# ---------- 埋め込み器 ----------
def embed_openai(chunks: List[str]) -> np.ndarray:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY が未設定です。PowerShell で $env:OPENAI_API_KEY='sk-...' を実行してください。")
    client = OpenAI(api_key=api_key)

    vecs: List[List[float]] = []
    BATCH = 128
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]
        res = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vecs.extend([d.embedding for d in res.data])
    arr = np.array(vecs, dtype="float32")
    if arr.shape[1] != EMBED_DIM:
        raise RuntimeError(f"埋め込み次元が想定と違います: got {arr.shape[1]} vs EMBED_DIM {EMBED_DIM}")
    return arr


def embed_sbert(chunks: List[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    arr = np.asarray(model.encode(chunks, show_progress_bar=True, normalize_embeddings=True), dtype="float32")
    if arr.shape[1] != EMBED_DIM:
        raise RuntimeError(f"埋め込み次元が想定と違います: got {arr.shape[1]} vs EMBED_DIM {EMBED_DIM}")
    return arr


def build():
    print(f"=== Step 1: texts.json 読み込み ===")
    items = load_texts(TEXTS_JSON)
    print(f"[info] loaded items: {len(items)}")

    chunks = [it["text"] for it in items]
    ids    = [it["id"]   for it in items]
    urlmap = {it["id"]: it.get("url", "") for it in items}

    print(f"=== Step 2: ベクトル化 & インデックス構築 ===")
    print(f"[info] encoding with '{EMBED_MODEL}', dim={EMBED_DIM} ...")

    if EMBED_BACKEND in ("openai", "oai"):
        vecs = embed_openai(chunks)
    else:
        vecs = embed_sbert(chunks)

    # FAISS (内積) インデックス
    index = faiss.IndexFlatIP(EMBED_DIM)
    faiss.normalize_L2(vecs)     # 内積検索のため正規化
    index.add(vecs)

    # 保存
    faiss.write_index(index, str(FAISS_IDX))
    with ID_MAP.open("w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)
    with DOC_MAP.open("w", encoding="utf-8") as f:
        json.dump(urlmap, f, ensure_ascii=False, indent=2)
    with META_JSON.open("w", encoding="utf-8") as f:
        json.dump({"dim": EMBED_DIM, "model": EMBED_MODEL, "backend": EMBED_BACKEND}, f, ensure_ascii=False, indent=2)

    print("[ok] wrote:", FAISS_IDX.name, ID_MAP.name, DOC_MAP.name, META_JSON.name)
    print("[done] total:", len(items), "dim:", EMBED_DIM)


if __name__ == "__main__":
    build()
