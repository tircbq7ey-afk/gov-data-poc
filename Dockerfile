# ---- base ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 必要ならここに requirements.txt を置く
# 例: COPY requirements.txt .
# RUN pip install -r requirements.txt

# 依存が少ない前提で uvicorn/fastapi を直接入れる
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./qa_service.py /app/qa_service.py

# 8010 を使う
EXPOSE 8010

# ヘルスチェック用にcurl（任意）
RUN apt-get update -y && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 起動
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
