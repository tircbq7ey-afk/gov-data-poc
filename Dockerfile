FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存（最小構成）
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# 必要フォルダ
RUN mkdir -p /app/www /app/data/feedback /app/data/flags

# アプリ
COPY app/qa_service.py /app/qa_service.py
# 静的ファイル（任意。あれば配信される）
COPY app/www /app/www

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
