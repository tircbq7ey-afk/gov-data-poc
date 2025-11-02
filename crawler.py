# -*- coding: utf-8 -*-
# crawler.py  (差分検知 + seed自体も保存 + ディレクトリURL対応 + robots無視オプション)
import argparse, hashlib, os, time, urllib.parse, json
from pathlib import Path
from typing import Iterable, Set, Tuple, List, Dict, Any

import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

RAW_DIR  = Path("data/raw")
META_DIR = Path("data/meta")
MANIFEST = META_DIR / "manifest.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TIMEOUT = 30
RETRY = 2
SLEEP = 1.0

# 末尾 / も HTML として扱うため "" を許可
ALLOW_EXT = {".pdf", ".html", ".htm", ""}
DISALLOW_QUERY = True
MAX_PER_DOMAIN_DEFAULT = 50

# ---------- utils ----------
def read_json(p: Path, default):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def norm_url(u: str) -> str:
    u = u.strip()
    if not u: return ""
    if DISALLOW_QUERY:
        sp = urllib.parse.urlsplit(u)
        u = urllib.parse.urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))
    return u

def url_ext(u: str) -> str:
    path = urllib.parse.urlsplit(u).path
    return os.path.splitext(path)[1].lower()

def url_domain(u: str) -> str:
    return urllib.parse.urlsplit(u).netloc.lower()

def requests_sesh() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.8",
    })
    return s

def load_robots(base: str) -> RobotFileParser:
    sp = urllib.parse.urlsplit(base)
    robots = f"{sp.scheme}://{sp.netloc}/robots.txt"
    r = RobotFileParser()
    try:
        r.set_url(robots); r.read()
    except Exception:
        r.parse(["User-agent: *", "Allow: /"])
    return r

# ---------- fetch & save ----------
def fetch_with_conditional(s: requests.Session, u: str, old: Dict[str,Any] | None):
    hdr = {}
    if old:
        if old.get("etag"): hdr["If-None-Match"] = old["etag"]
        if old.get("last_modified"): hdr["If-Modified-Since"] = old["last_modified"]
    code = 0; headers = {}
    for i in range(RETRY + 1):
        try:
            r = s.get(u, headers=hdr, timeout=TIMEOUT, allow_redirects=True)
            code = r.status_code
            if code in (200, 304):
                return code, (r.content if code == 200 else b""), dict(r.headers)
        except Exception:
            code = 0
        time.sleep(0.5 * (i + 1))
    return code, b"", headers

def save_or_decide(url: str, content: bytes, headers: Dict[str,str], old: Dict[str,Any] | None) -> tuple[bool, Path | None, Dict[str,Any]]:
    """return: (parse_needed, saved_path, new_meta)"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    ext = url_ext(url) or ".html"
    path = RAW_DIR / f"{url_hash}{ext}"

    if content:
        content_hash = hashlib.sha256(content).hexdigest()
    else:
        content_hash = old.get("content_hash") if old else None

    parse_needed = (not old) or (old.get("content_hash") != content_hash)

    # 書き込みは「変更があった時だけ」上書き
    if content and parse_needed:
        path.write_bytes(content)

    meta = {
        "url": url,
        "path": str(path),
        "content_hash": content_hash,
        "content_type": headers.get("Content-Type"),
        "last_modified": headers.get("Last-Modified"),
        "etag": headers.get("ETag"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parse_needed": parse_needed,
        "doc_id": (old or {}).get("doc_id")  # parseで更新される
    }
    return parse_needed, (path if content and parse_needed else None), meta

# ---------- crawling ----------
def absolutize(base: str, link: str) -> str:
    return urllib.parse.urljoin(base, link)

def extract_links(base_url: str, html: bytes) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    out=[]
    for a in soup.find_all("a", href=True):
        u = absolutize(base_url, a["href"])
        u = norm_url(u)
        if not u: continue
        if url_ext(u) in ALLOW_EXT: out.append(u)
    return out

def crawl_page_for_assets(s: requests.Session, base_url: str, robots: RobotFileParser, ignore_robots: bool) -> Set[str]:
    code, html, _ = fetch_with_conditional(s, base_url, None)
    if code != 200: return set()
    found=set()
    for u in extract_links(base_url, html):
        if (not ignore_robots) and (not robots.can_fetch(UA, u)): continue
        if url_domain(u) != url_domain(base_url): continue
        if url_ext(u) in ALLOW_EXT: found.add(u)
    return found

def crawl_and_record(s: requests.Session, u: str, robots: RobotFileParser, ignore_robots: bool, manifest: Dict[str,Any]):
    if (not ignore_robots) and (not robots.can_fetch(UA, u)):
        print(f"[deny] robots.txt blocks: {u}"); return

    old = manifest.get(u)
    code, data, hdr = fetch_with_conditional(s, u, old)
    if code in (200, 304):
        parse_needed, saved, meta = save_or_decide(u, data, hdr, old)
        manifest[u] = meta
        print(f"[ok] {u} status={code} parse_needed={parse_needed} file={Path(meta['path']).name}")
    else:
        print(f"[skip] {u} code={code}")

def bulk_crawl_from_seeds(seeds: Iterable[str], max_per_domain: int, ignore_robots: bool):
    s = requests_sesh()
    META_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(MANIFEST, {})

    robots_cache: dict[str, RobotFileParser] = {}
    count_by_domain: dict[str, int] = {}
    candidate: Set[str] = set()

    seeds = [norm_url(u) for u in seeds if u.strip()]
    for seed in seeds:
        dom = url_domain(seed)
        if dom not in robots_cache: robots_cache[dom] = load_robots(seed)
        rob = robots_cache[dom]

        print(f"[seed] {seed}")

        # seed自体も候補に入れる（.html/.pdf/末尾/）
        if url_ext(seed) in ALLOW_EXT: candidate.add(seed)

        try:
            links = crawl_page_for_assets(s, seed, rob, ignore_robots)
            print(f"  -> found {len(links)} links on seed")
        except Exception as e:
            print(f"[warn] seed fetch failed: {seed} : {e}")
            links=set()

        for u in links:
            if url_ext(u) in ALLOW_EXT: candidate.add(u)
        time.sleep(SLEEP)

    fetched=0
    for u in sorted(candidate):
        dom = url_domain(u)
        n = count_by_domain.get(dom, 0)
        if n >= max_per_domain: continue
        rob = robots_cache.get(dom) or load_robots(u)
        crawl_and_record(s, u, rob, ignore_robots, manifest)
        count_by_domain[dom] = n + 1
        fetched += 1
        time.sleep(SLEEP)

    write_json(MANIFEST, manifest)
    print(f"[done] fetched={fetched} domains={len(count_by_domain)} manifest={MANIFEST}")

def crawl_explicit_urls(urls: Iterable[str], ignore_robots: bool):
    s = requests_sesh()
    META_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(MANIFEST, {})
    for u in urls:
        u = norm_url(u)
        if not u: continue
        rob = load_robots(u)
        crawl_and_record(s, u, rob, ignore_robots, manifest)
        time.sleep(SLEEP)
    write_json(MANIFEST, manifest)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=str, help="入口URLリスト（1行1URL）")
    ap.add_argument("--urls", type=str, nargs="*", help="直接ダウンロードするURL群")
    ap.add_argument("--max-per-domain", type=int, default=MAX_PER_DOMAIN_DEFAULT)
    ap.add_argument("--ignore-robots", action="store_true", help="robots.txt を無視して取得（検証用）")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.seeds:
        path = Path(args.seeds)
        if not path.exists(): raise FileNotFoundError(args.seeds)
        seeds = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        bulk_crawl_from_seeds(seeds, args.max_per_domain, args.ignore_robots)
    elif args.urls:
        crawl_explicit_urls(args.urls, args.ignore_robots)
    else:
        msg = (
            "Usage:\n"
            "  python crawler.py --seeds seeds.txt [--max-per-domain 50] [--ignore-robots]\n"
            "  or\n"
            "  python crawler.py --urls <url1> <url2> ... [--ignore-robots]\n"
        )
        print(msg)

if __name__ == "__main__":
    main()
