# gov-data-poc

自治体データ基盤のPoC向けシンプルQA API。  
- Framework: FastAPI + Uvicorn
- Nginx でリバースプロキシ（:8080→:8010）
- FAQの初期データ `data/faq.json`
- フィードバックは JSONL で `/data/feedback/*.jsonl` に追記

## 構成
