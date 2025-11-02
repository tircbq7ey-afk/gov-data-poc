# -*- coding: utf-8 -*-
# embed.py  (差分更新：旧チャンクremove→新チャンクadd／OpenAI or ローカル)
from __future__ import annotations
import os, json, hashlib, struct
from pathlib import Path
from typing import List, Dict
import numpy as np
import faiss

BASE = Path(__file__).resolve().parent
DB_DIR     = BASE / "data" / "db"
PARSED_DIR = BASE / "data" / "parsed"
OUT_INDEX  = DB_DIR / "faiss.index"
OUT_JSONL  = DB_DIR / "texts.json"
ID_MAP     = DB_DIR / "id_map.json"   # chunk_id -> int64
DOC_MAP    = DB_DIR / "doc_map.json"  # doc_id   -> [chunk_id,...]

EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
BATCH = 128

# -------- utils --------
def read_json(p: Path, default):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def str_to_i64(s: str) -> int:
    h = hashlib.sha1(s.encode("utf-8")).digest()
    return struct.unpack(">q", h[:8])[0]  # 符号ありint64（Overflow対策）

def load_index(dim: int) -> faiss.IndexIDMap2:
    if OUT_INDEX.exists():
        idx = faiss.read_index(str(OUT_INDEX))
        if idx.d != dim:
            base = faiss.IndexFlatIP(dim)
            return faiss.IndexIDMap2(base)
        if not isinstance(idx, faiss.IndexIDMap2):
            idx = faiss.IndexIDMap2(idx)
        return idx
    base = faiss.IndexFlatIP(dim)
    return faiss.IndexIDMap2(base)

def jsonl_rows(p: Path) -> list[dict]:
    rows=[]
    if not p.exists(): return rows
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: rows.append(json.loads(ln))
    return rows

# -------- embedders --------
def _embed_openai(texts: List[str]) -> np.ndarray:
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY が未設定です。")
    client = OpenAI(api_key=OPENAI_API_KEY)
    vecs=[]
    for i in range(0, len(texts), BATCH):
        part = texts[i:i+BATCH]
        res = client.embeddings.create(model=EMBEDDING_MODEL, input=part)
        vecs.extend([d.embedding for d in res.data])
    arr = np.asarray(vecs, dtype="float32"); faiss.normalize_L2(arr); return arr

def _embed_local_builder():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    dim = int(model.get_sentence_embedding_dimension())
    def _fn(texts: List[str]) -> np.ndarray:
        vecs=[]
        for i in range(0, len(texts), BATCH):
            part = texts[i:i+BATCH]
            X = model.encode(part, normalize_embeddings=True)
            vecs.append(np.asarray(X, dtype="float32"))
        arr = np.vstack(vecs) if vecs else np.zeros((0, dim), dtype="float32")
        faiss.normalize_L2(arr); return arr
    return _fn, dim

def choose_embedder():
    if OPENAI_API_KEY: return _embed_openai, 1536
    try: return _embed_local_builder()
    except Exception: raise RuntimeError("埋め込み手段がありません。")

# -------- main --------
def main():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 現在のdoc（parsed）をロード
    parsed_docs=[]
    for p in sorted(PARSED_DIR.glob("*.json")):
        parsed_docs.append(read_json(p, {}))
    if not parsed_docs:
        # フォールバック：JSONLからdoc_id/chunk_idを再構築（最低限）
        rows = jsonl_rows(OUT_JSONL)
        if not rows:
            print("[embed] 入力データがありません。parse.py を先に実行してください。"); return
        # 疑似doc構築（doc_idごとに束ねる）
        by_doc: Dict[str, list[dict]] = {}
        for r in rows:
            by_doc.setdefault(r.get("doc_id","unknown"), []).append({"chunk_id": r["id"], "text": r["text"]})
        for d, lst in by_doc.items():
            parsed_docs.append({"doc_id": d, "chunks": lst})

    # 2) 既存メタとindex
    id_map  = read_json(ID_MAP, {})
    doc_map = read_json(DOC_MAP, {})
    embed_fn, dim = choose_embedder()
    index = load_index(dim)

    # 3) 差分適用
    current_doc_ids = set()
    for doc in parsed_docs:
        doc_id = doc.get("doc_id"); current_doc_ids.add(doc_id)
        new_chunk_ids = {c["chunk_id"] for c in doc.get("chunks", [])}
        old_chunk_ids = set(doc_map.get(doc_id, []))

        to_remove = list(old_chunk_ids - new_chunk_ids)
        to_add    = [c for c in doc.get("chunks", []) if c["chunk_id"] not in old_chunk_ids]

        # remove
        if to_remove:
            rm_ids = [id_map[cid] for cid in to_remove if cid in id_map]
            if rm_ids:
                index.remove_ids(np.array(rm_ids, dtype=np.int64))
            for cid in to_remove: id_map.pop(cid, None)

        # add
        if to_add:
            texts = [c["text"] for c in to_add]
            vecs  = embed_fn(texts)
            add_ids=[str_to_i64(c["chunk_id"]) for c in to_add]
            for cid, iid in zip([c["chunk_id"] for c in to_add], add_ids):
                id_map[cid] = iid
            index.add_with_ids(vecs, np.array(add_ids, dtype=np.int64))

        # doc_mapを最新化
        doc_map[doc_id] = list(new_chunk_ids)
        if to_remove or to_add:
            print(f"[embed] doc={doc_id} add={len(to_add)} remove={len(to_remove)}")

    # 4) 既存indexにあって、parsed側から消えたdocは丸ごと削除
    vanished_docs = set(doc_map.keys()) - current_doc_ids
    for doc_id in vanished_docs:
        rm_ids = [id_map[cid] for cid in doc_map.get(doc_id, []) if cid in id_map]
        if rm_ids:
            index.remove_ids(np.array(rm_ids, dtype=np.int64))
        for cid in doc_map.get(doc_id, []):
            id_map.pop(cid, None)
        doc_map.pop(doc_id, None)
        print(f"[embed] doc={doc_id} removed(all)")

    # 5) 保存
    faiss.write_index(index, str(OUT_INDEX))
    write_json(ID_MAP, id_map)
    write_json(DOC_MAP, doc_map)
    print(f"[embed] 完了：ntotal={index.ntotal}, docs={len(doc_map)}")

if __name__ == "__main__":
    main()
