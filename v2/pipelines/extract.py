import re, fitz, requests
from bs4 import BeautifulSoup
def clean_text(t: str) -> str:
    t = re.sub(r"\s+\n", "\n", t)
    t = re.sub(r"\n{2,}", "\n\n", t)
    return t.strip()
def extract_from_pdf(url):
    with fitz.open(stream=requests.get(url, timeout=30).content, filetype="pdf") as doc:
        text = "\n".join(page.get_text() for page in doc)
    return clean_text(text)
def extract_from_html(url):
    html = requests.get(url, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script","style","noscript"]): s.decompose()
    text = soup.get_text("\n")
    title = (soup.title.string if soup.title else "出典").strip()
    return title, clean_text(text)
