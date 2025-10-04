# build_index.py
from pathlib import Path
import os, json, time
import numpy as np
import faiss

DATA = Path("data/db")
TEXTS_JSON = DATA / "texts.json"
INDEX_PATH = DATA / "faiss.index"
ID_MAP = DATA / "id_map.json"
DOC_MAP = DATA / "doc_map.json"
META = DATA / "meta.json"

MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
DIM = int(os.environ.get("EMBED_DIM", "1536"))

def read_texts(path: Path):
    raw = path.read_text(encoding="utf-8-sig")  # BOM を無害化
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("texts.json は JSON 配列である必要があります。")
    norm = []
    for i, it in enumerate(data):
        if isinstance(it, str):
            norm.append({"id": f"item-{i:05d}", "title": "text", "text": it,
                         "source_url": None, "source_path": "local"})
        else:
            norm.append({
                "id": str(it.get("id", f"item-{i:05d}")),
                "title": it.get("title", "text"),
                "text": it["text"],
                "source_url": it.get("source_url"),
                "source_path": it.get("source_path", "local")
            })
    return norm

def embed_texts(texts):
    # OpenAI か SBERT かを自動判定
    if MODEL.startswith("text-embedding-"):
        from openai import OpenAI
        client = OpenAI()
        # 分割して投げる（大きいとき用）
        BATCH = 256
        vecs = []
        for s in range(0, len(texts), BATCH):
            batch = [t["text"] for t in texts[s:s+BATCH]]
            r = client.embeddings.create(model=MODEL, input=batch)
            vecs.extend([d.embedding for d in r.data])
        arr = np.array(vecs, dtype="float32")
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL)
        arr = model.encode([t["text"] for t in texts], show_progress_bar=True)
        arr = np.asarray(arr, dtype="float32")
    # cosine用に正規化
    faiss.normalize_L2(arr)
    return arr

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    assert TEXTS_JSON.exists(), f"{TEXTS_JSON} がありません。"

    items = read_texts(TEXTS_JSON)
    print(f"[info] loaded items: {len(items)}")

    print(f"=== Step 2: ベクトル化 & インデックス構築 ===")
    print(f"[info] model={MODEL}, dim={DIM}")
    X = embed_texts(items)
    if X.shape[1] != DIM:
        raise ValueError(f"次元不一致: EMBED_DIM={DIM}, 実ベクトル次元={X.shape[1]}")

    index = faiss.IndexFlatIP(DIM)
    index.add(X)

    # 書き出し
    faiss.write_index(index, str(INDEX_PATH))
    ID_MAP.write_text(json.dumps([it["id"] for it in items], ensure_ascii=False, indent=2), encoding="utf-8")
    DOC_MAP.write_text(json.dumps(
        {i: {"title": it["title"], "source_url": it.get("source_url"), "source_path": it.get("source_path")}
         for i, it in enumerate(items)}, ensure_ascii=False, indent=2), encoding="utf-8")
    META.write_text(json.dumps({"ntotal": int(index.ntotal), "dim": DIM, "ts": time.time()},
                               ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ok] wrote: {INDEX_PATH}")
    print(f"[ok] wrote: {ID_MAP}, {DOC_MAP}, {META}")
    print(f"[done] ntotal={index.ntotal}, dim={DIM}")

if __name__ == "__main__":
    main()
