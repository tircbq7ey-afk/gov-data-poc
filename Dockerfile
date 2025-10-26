# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data \
    API_TOKEN=changeme-local-token

WORKDIR /app

# 依存
RUN pip install --no-cache-dir fastapi uvicorn

# ディレクトリ
RUN mkdir -p /app/www /app/data/flags /app/data/feedback

# アプリと静的ファイルをコピー
COPY app/qa_service.py /app/qa_service.py
# index.html を置いている場合（なければスキップ可）
COPY app/www/ /app/www/

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
