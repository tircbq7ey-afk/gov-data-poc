FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data
    API_TOKEN=changeme-local-token
WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

# ここはあなたの構成に合わせて
COPY qa_service.py /app/qa_service.py
COPY app/www /app/www

RUN mkdir -p /app/data /app/data/feedback /app/data/flags

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
