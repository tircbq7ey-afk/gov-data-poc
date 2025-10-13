# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ---- Python ランタイム設定（ログ即時出力・pyc無効）----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---- 作業ディレクトリ ----
WORKDIR /app

# ---- 必要最小限のツール（curl だけ）----
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# ---- 最小パッケージ（FastAPI + Uvicorn）----
RUN pip install --no-cache-dir fastapi uvicorn

# ---- アプリとデータを配置 ----
# リポジトリ直下に qa_service.py がある前提（ログのビルド履歴と合わせています）
COPY ./qa_service.py /app/qa_service.py
# データがあれば一緒にコピー（存在しない場合は無視してOK）
# 例: COPY ./data /app/data

# ---- 公開ポート ----
EXPOSE 8010

# ---- コンテナのヘルスチェック (/health) ----
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8010/health || exit 1

# ---- 起動コマンド ----
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
