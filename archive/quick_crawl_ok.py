# quick_crawl_ok.py
import pathlib, time, requests, sys

# ここは「確実に 200 で開けるページ」を入れておきます
# 必要に応じて増減OK。手元のブラウザで一度開けることを確認してから入れるのがコツ。
URLS = [
    "https://www.moj.go.jp/isa/",               # 出入国在留管理庁 トップ
    "https://www.e-gov.go.jp/help/flow.html",   # e-Gov ヘルプ（フロー）
    "https://www.digital.go.jp/",               # デジタル庁 トップ
]

out = pathlib.Path("data/raw")
out.mkdir(parents=True, exist_ok=True)

def fetch(url: str, n: int) -> None:
    print("GET", url)
    for attempt in range(1, 4):  # 最大3回リトライ
        try:
            r = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            # 404 や 403 は例外化してスキップ理由を明示
            r.raise_for_status()
            p = out / f"page_{n:03d}.html"
            p.write_bytes(r.content)
            print("WROTE", p.resolve(), "bytes:", len(r.content))
            return
        except requests.exceptions.HTTPError as e:
            print(f"  [HTTP {r.status_code}] {url}  (try {attempt}/3)")
            if 400 <= r.status_code < 500:
                # 4xx はリトライしても無駄なことが多いので即中断
                raise
            time.sleep(1)
        except Exception as e:
            print("  [ERROR]", e, f"(try {attempt}/3)")
            time.sleep(1)
    raise RuntimeError(f"failed to fetch: {url}")

def main():
    for i, u in enumerate(URLS, 1):
        fetch(u, i)
        time.sleep(1)  # 連続アクセスを少し間隔

if __name__ == "__main__":
    sys.exit(main())
