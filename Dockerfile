FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 必要ディレクトリ
RUN mkdir -p /app/www /app/data/feedback /app/data/flags

# アプリ本体
COPY app/qa_service.py /app/qa_service.py
# Web 資材（app/www/index.html など）を丸ごとコピー
COPY app/www /app/www

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
