# -*- coding: utf-8 -*-
# parse.py  (差分パース：manifestのparse_neededだけ更新／fallbackはraw全量)
import os, json, re, hashlib
from pathlib import Path
from datetime import datetime, UTC
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
RAW_DIR     = BASE / "data" / "raw"
PARSED_DIR  = BASE / "data" / "parsed"
DB_DIR      = BASE / "data" / "db"
META_DIR    = BASE / "data" / "meta"
OUT_JSONL   = DB_DIR / "texts.json"        # JSON Lines（1行=1チャンク）
MANIFEST    = META_DIR / "manifest.json"   # url毎の状態

ALLOW_EXT = {".html", ".htm", ".pdf"}
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# -------- utils --------
def read_json(p: Path, default):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def load_jsonl(p: Path) -> list[dict]:
    if not p.exists(): return []
    rows=[]
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: rows.append(json.loads(ln))
    return rows

def save_jsonl(p: Path, rows: list[dict]):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def norm_ws(s: str) -> str:
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    out=[]; n=len(text); i=0
    while i<n:
        j=min(i+size, n)
        out.append(text[i:j])
        if j==n: break
        i=max(0, j-overlap)
    return out

# -------- extractors --------
def html_to_text(path: Path) -> tuple[str,str]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript","iframe"]): t.decompose()
    title = (soup.title.string or "").strip() if soup.title else path.stem
    text = norm_ws(soup.get_text("\n"))
    return text, title

def pdf_to_text(path: Path) -> tuple[str,str]:
    # 1) pdfminer
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(path))
        if text and len(text.strip())>50: return norm_ws(text), path.stem
    except Exception: pass
    # 2) PyMuPDF
    try:
        import fitz
        buf=[]
        with fitz.open(str(path)) as doc:
            for p in doc: buf.append(p.get_text())
        return norm_ws("\n".join(buf)), path.stem
    except Exception:
        return "", path.stem

# -------- main --------
def main():
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    manifest = read_json(MANIFEST, {})
    targets: list[tuple[str, Path, dict]] = []

    if manifest:
        # 差分：parse_needed=True のみ対象
        for url, meta in manifest.items():
            if meta.get("parse_needed"):
                p = Path(meta["path"])
                if p.exists(): targets.append((url, p, meta))
        if not targets:
            print("[parse] 差分なし。処理をスキップします。")
            return
    else:
        # フォールバック：raw 全量
        for p in RAW_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in ALLOW_EXT:
                targets.append((f"file://{p.name}", p, {"content_hash": sha256_text(p.read_bytes().hex()[:4096])}))
        if not targets:
            print("[parse] 対象がありません。まず crawler を実行してください。")
            return

    rows = load_jsonl(OUT_JSONL)
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

    for url, raw_path, meta in targets:
        ext = raw_path.suffix.lower()
        if ext in (".html",".htm"):
            text, title = html_to_text(raw_path)
        elif ext == ".pdf":
            text, title = pdf_to_text(raw_path)
        else:
            print(f"[parse] skip (ext): {raw_path.name}")
            continue

        content_hash = meta.get("content_hash") or sha256_text(raw_path.read_bytes().hex()[:4096])
        # doc_id は URL + content_hash で決定（変更があれば doc_id も変わる）
        doc_id = sha256_text(f"{url}|{content_hash}")
        old_doc_id = meta.get("doc_id")

        # 旧parsedの掃除（doc_idが変わった場合）
        if old_doc_id and old_doc_id != doc_id:
            old_p = PARSED_DIR / f"{old_doc_id}.json"
            if old_p.exists():
                try: old_p.unlink()
                except Exception: pass

        chunks = chunk_text(text)
        doc_json = {
            "doc_id": doc_id, "url": url, "content_hash": content_hash, "title": title,
            "chunks": [
                {"chunk_index": i, "chunk_id": sha256_text(doc_id + f"#{i}:" + sha256_text(c)), "text": c}
                for i, c in enumerate(chunks)
            ]
        }
        (PARSED_DIR / f"{doc_id}.json").write_text(json.dumps(doc_json, ensure_ascii=False, indent=2), encoding="utf-8")

        # texts.json(JSONL) 差し替え：旧doc行を削除 → 新行を追加
        before = len(rows)
        rows = [r for r in rows if r.get("doc_id") not in {old_doc_id, doc_id}]
        removed = before - len(rows)
        for c in doc_json["chunks"]:
            rows.append({
                "id": c["chunk_id"], "doc_id": doc_id, "source_path": str(raw_path), "source_url": url,
                "title": title, "ext": ext.lstrip("."), "chars": len(c["text"]), "text": c["text"], "created_at": now
            })

        # manifest 更新（parse_needed を下げ、doc_id を最新へ）
        if url.startswith("http"):
            manifest[url]["parse_needed"] = False
            manifest[url]["doc_id"] = doc_id

        print(f"[parse] {raw_path.name} -> chunks={len(chunks)} replace_rows: -{removed} +{len(doc_json['chunks'])}")

    save_jsonl(OUT_JSONL, rows)
    if manifest: write_json(MANIFEST, manifest)
    print(f"[parse] 完了：texts.json を差分更新しました。")

if __name__ == "__main__":
    main()
