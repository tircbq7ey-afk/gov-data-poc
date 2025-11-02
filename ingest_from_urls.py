# ingest_from_urls.py
import os, re, json, sys, time
from pathlib import Path
from typing import List, Dict
import hashlib
import requests

from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pdfminer.high_level import extract_text as pdf_extract

USER_AGENT = os.getenv("USER_AGENT", "gov-data-poc/1.0")
DB = Path("data/db")
TEXTS = DB / "texts.json"

def read_existing() -> List[Dict]:
    if TEXTS.exists():
        return json.loads(TEXTS.read_text(encoding="utf-8-sig"))
    return []

def normalize_ws(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s

def url_to_id(u: str) -> str:
    h = hashlib.md5(u.encode("utf-8")).hexdigest()[:10]
    host = urlparse(u).netloc.replace("www.","").replace(".","-")
    return f"{host}-{h}"

def fetch(u: str) -> bytes:
    resp = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.content

def html_to_text(b: bytes) -> (str, str):
    soup = BeautifulSoup(b, "html.parser")
    title = normalize_ws(soup.title.get_text()) if soup.title else ""
    # main contentを素朴に抽出
    for s in soup(["script","style","noscript"]): s.decompose()
    text = normalize_ws(soup.get_text(" "))
    return title, text

def pdf_to_text(b: bytes) -> (str, str):
    # 一時ファイルに書いてpdfminerで抽出
    tmp = Path("tmp_ingest.pdf")
    tmp.write_bytes(b)
    text = normalize_ws(pdf_extract(str(tmp)))
    tmp.unlink(missing_ok=True)
    return "", text

def ingest(urls: List[str], mode: str):
    DB.mkdir(parents=True, exist_ok=True)
    data = read_existing()
    by_id = {str(r.get("id")): r for r in data}

    out = data[:]  # 既存をベース
    for u in urls:
        u = u.strip()
        if not u: continue
        try:
            b = fetch(u)
            if u.lower().endswith(".pdf") or b[:4] == b"%PDF":
                title, text = pdf_to_text(b)
            else:
                title, text = html_to_text(b)
            if not title:
                title = u
            rid = url_to_id(u)
            rec = {
                "id": rid,
                "title": title,
                "text": text,
                "source_url": u,
                "source_path": "web"
            }
            if mode == "append" and rid in by_id:
                # 既存あり→スキップ
                continue
            if mode == "overwrite" and rid in by_id:
                # 上書き
                for i, r in enumerate(out):
                    if r.get("id") == rid:
                        out[i] = rec
                        break
            else:
                out.append(rec)
            time.sleep(0.5)  # 優しめ
            print(f"[ok] {u}")
        except Exception as e:
            print(f"[ng] {u} -> {e}")

    TEXTS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote: {TEXTS} (records={len(out)})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python ingest_from_urls.py urls.txt [append|overwrite]")
        sys.exit(1)
    urls_file = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) >= 3 else "append"
    urls = [l.strip() for l in urls_file.read_text(encoding="utf-8").splitlines()]
    ingest(urls, mode)
