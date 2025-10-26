# Copilot Instructions (gov-data-poc)

- FastAPI サービス:
  - `GET /ask` : クエリ `q` (必須), `lang`(既定 ja)。JSONで `{q, lang, answer, sources}` を返す。
  - `POST /feedback` : body {q, answer, sources[], lang, label?} を JSONL として `./data/feedback/YYYYMMDD.jsonl` に追記。
- 注意:
  - `/ask` は **GET**。POST は 405 を返すのが正しい。
  - `/admin/reindex` は **未実装**。必要なら新規で作る（200 で `{"ok": true}` を返し、`./data/flags/reindex` を touch）。
  - ディレクトリ `./data/feedback`, `./data/flags` は起動時に必ず `exist_ok=True` で作成。
  - 認証は `x-api-key` ヘッダ。`API_TOKEN` 環境変数（dev 既定: `changeme-local-token`）。
- 期待する自動テスト:
  - `GET /ask?q=...` が 200。
  - `POST /feedback` が 200 かつ JSONL 追記。
  - `/admin/reindex` が 200（実装した場合）。
