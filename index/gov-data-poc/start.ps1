param([switch]$NoIndex)

Set-Location -Path "$PSScriptRoot"
Set-ExecutionPolicy -Scope Process RemoteSigned -Force
if (!(Test-Path .\venv\Scripts\Activate.ps1)) { throw "venv がありません" }
.\venv\Scripts\Activate.ps1

if (Test-Path .env) {
  Write-Host "Loading .env ..."
} else {
  Write-Warning ".env がありません。 .env.example を参考に作成してください。"
}

pip install -r .\requirements.txt

if (-not $NoIndex) {
  python .\bm25_index.py
  python .\build_bm25.py
}

uvicorn qa_service:app --host 127.0.0.1 --port 8010 --reload
