from fastapi.testclient import TestClient
from app.main import APP
c = TestClient(APP)
def test_health():
    r = c.get("/health"); assert r.status_code == 200
def test_search():
    r = c.post("/search", json={"query":"在留資格 変更 手続き"})
    assert r.status_code == 200
    assert "answer" in r.json()
