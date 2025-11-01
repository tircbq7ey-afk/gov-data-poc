# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# アプリ本体
COPY app/qa_service.py /app/qa_service.py

# 静的ファイル（任意: app/www/index.html がある場合に配信）
COPY app/www /app/www

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
