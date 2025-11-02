# -*- coding: utf-8 -*-
import os, json, time, hashlib, re
from datetime import datetime
from typing import List, Dict, Any

def ensure_dirs(paths: List[str]):
    for p in paths:
        os.makedirs(p, exist_ok=True)

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def read_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def to_safe_filename(name: str, maxlen=64):
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:maxlen]

def chunk_text(text: str, size: int, overlap: int) -> List[str]:
    # 改行・空白の整理
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + size, n)
        chunk = text[i:end]
        chunks.append(chunk)
        if end == n: break
        i = end - overlap
        if i < 0: i = 0
    return chunks

def string_id_to_int64(s: str) -> int:
    # FAISSのIDに使うint64（ハッシュの先頭8バイト）
    h = hashlib.sha1(s.encode("utf-8")).digest()
    return int.from_bytes(h[:8], byteorder="big", signed=False)

def trim_tokens(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
