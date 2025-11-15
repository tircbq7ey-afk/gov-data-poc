import requests
import fitz  # PyMuPDF

from bs4 import BeautifulSoup  # 既にあればそのまま、なければ pip install beautifulsoup4

def extract_from_pdf(url: str) -> str:
    """PDF からテキストを抽出。PDFでない場合はワーニングを出して空文字を返す。"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.content

    # 先頭数バイトを見て PDF っぽいかチェック
    if not data.startswith(b"%PDF"):
        print(f"[WARN] Not a valid PDF at {url}. content-type={resp.headers.get('content-type')}")
        return ""

    with fitz.open(stream=data, filetype="pdf") as doc:
        texts = []
        for page in doc:
            texts.append(page.get_text())
    return "\n".join(texts)

def extract_from_html(url: str) -> str:
    """HTML からテキストを抽出"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n")
