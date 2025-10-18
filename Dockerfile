# ベース
FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリ
RUN pip install --no-cache-dir fastapi uvicorn \
    scikit-learn numpy

# アプリコード
COPY ./qa_service.py /app/qa_service.py

# ポート（uvicorn用）
EXPOSE 8010

# 起動コマンド
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
