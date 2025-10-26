# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存
RUN pip install --no-cache-dir fastapi uvicorn

# ディレクトリ作成
RUN mkdir -p /app/www /app/data/feedback /app/data/flags

# アプリ本体
COPY qa_service.py /app/qa_service.py

# Web公開物（app/www/index.html など）
COPY app/www /app/www

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
