FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data
ENV API_TOKEN=changeme-local-token

WORKDIR /app

# 依存最小
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ
COPY qa_service.py /app/qa_service.py
COPY app/www /app/www

# データ領域
RUN mkdir -p /app/data/feedback /app/data/flags

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
