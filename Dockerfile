FROM python:3.11-slim

WORKDIR /app

# ランタイムのみ最小限
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./app/qa_service.py /app/qa_service.py

# curl はデバッグ用に入れておくと便利
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

# ポート 8010 で待受（nginx からプロキシされる）
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
