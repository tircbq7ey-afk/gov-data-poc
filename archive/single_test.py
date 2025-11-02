import pathlib, hashlib, requests

URL = "https://www.moj.go.jp/isa/"   # ← seeds.txt 先頭ドメインの無害なURLにしてOK

OUT = pathlib.Path("data/raw")
OUT.mkdir(parents=True, exist_ok=True)

UA  = {"User-Agent": "gov-data-poc/1.0 (+single_test)"}

try:
    r = requests.get(URL, headers=UA, timeout=30, allow_redirects=True)
    ct = (r.headers.get("Content-Type") or "").lower()
    ok = any(x in ct for x in ("text/html", "application/pdf", "text/plain"))
    if r.status_code == 200 and ok and r.content:
        h   = hashlib.sha1(URL.encode()).hexdigest()[:16]
        ext = ".pdf" if "pdf" in ct else ".html"
        p   = OUT / f"single_test_{h}{ext}"
        p.write_bytes(r.content)
        print("SAVED", p.as_posix(), "bytes=", len(r.content), "ctype=", ct)
    else:
        print("NO_SAVE status=", r.status_code, "ctype=", ct, "len=", len(r.content))
except Exception as e:
    print("ERROR", type(e).__name__, e)
