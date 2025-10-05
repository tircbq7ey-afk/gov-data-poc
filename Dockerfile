FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# tools + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 先に作成＆権限
RUN useradd -m appuser && mkdir -p /var/log/app /data && \
    chown -R appuser:appuser /app /var/log/app /data

# アプリ本体
COPY . .
USER appuser

# ビルドメタ
ARG VERSION=dev BUILD_SHA=unknown BUILD_TIME=unknown
ENV VERSION=${VERSION} BUILD_SHA=${BUILD_SHA} BUILD_TIME=${BUILD_TIME}

# ← これで /app が import ルートになる
ENV PYTHONPATH=/app

EXPOSE 8010
# パッケージ記法に統一（最重要）
CMD ["python","-m","uvicorn","app.qa_service:app","--host","0.0.0.0","--port","8010","--workers","1"]
