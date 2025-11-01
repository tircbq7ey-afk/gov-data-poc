FROM python:3.11-slim

WORKDIR /app

# ランタイムに必要なものを最小限インストール
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# アプリ本体
COPY app/qa_service.py /app/qa_service.py

# データ置き場（コンテナ内）※ 実体は compose のボリュームでホストにマウント
RUN mkdir -p /app/data/feedback /app/data/flags

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
