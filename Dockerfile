FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存（requirements.txt が無ければ FastAPI/uvicorn を直接入れる）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || \
    pip install --no-cache-dir fastapi "uvicorn[standard]"

# 必要ディレクトリ
RUN mkdir -p /app/www /app/data/feedback /app/data/flags

# アプリ・Web
COPY qa_service.py /app/qa_service.py
# ローカルの app/www を丸ごと（index.html をここに置く）
COPY app/www /app/www

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
