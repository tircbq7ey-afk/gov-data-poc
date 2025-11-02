import requests, hashlib, os
from bs4 import BeautifulSoup

BASE_URL = "https://www.moj.go.jp/isa/"   # 出入国在留管理庁（例）
SAVE_DIR = "data/raw"

def fetch_pdfs():
    os.makedirs(SAVE_DIR, exist_ok=True)
    res = requests.get(BASE_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    for link in soup.find_all("a", href=True):
        if link["href"].endswith(".pdf"):
            url = link["href"]
            if not url.startswith("http"):
                url = BASE_URL + url
            fname = os.path.join(SAVE_DIR, os.path.basename(url))
            if not os.path.exists(fname):
                print("DL:", url)
                pdf = requests.get(url).content
                with open(fname, "wb") as f:
                    f.write(pdf)

if __name__ == "__main__":
    fetch_pdfs()
