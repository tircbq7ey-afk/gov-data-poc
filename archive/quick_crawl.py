import pathlib, requests, time
out = pathlib.Path("data/raw"); out.mkdir(parents=True, exist_ok=True)

# 必要ならURLを増やしてください（官公庁の安全なページを例示）
URLS = [
    "https://www.digital.go.jp/faq/",          # デジタル庁 FAQ
    "https://www.moj.go.jp/isa/nyuukokukanri01_00001.html",  # 入国・在留情報(例)
    "https://www.e-gov.go.jp/help/flow.html"
]

for i, u in enumerate(URLS, 1):
    print("GET", u)
    r = requests.get(u, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    path = out / f"page_{i:02d}.html"
    path.write_bytes(r.content)
    print("WROTE", path.resolve(), "bytes:", len(r.content))
    time.sleep(1)   # 連続アクセスを少し間隔
