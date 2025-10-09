# tools/smoke.ps1 — 疎通テスト（Windows）
param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string]$EnvFile = ".env",
  [string]$Lang = "ja",
  [string]$Query = "パスポート更新の手続きは？"
)

Write-Host "== smoke test =="
if (-not (Test-Path $EnvFile)) {
  Write-Warning "Env file not found: $EnvFile (API_TOKEN 未設定なら未認証で実行します)"
  $API_TOKEN = ""
} else {
  $line = (Get-Content $EnvFile | Select-String '^API_TOKEN=' | Select -First 1).ToString()
  $API_TOKEN = if ($line) { $line.Split('=')[1].Trim() } else { "" }
}

# /health
Write-Host "`n[1] GET /health"
curl.exe "$BaseUrl/health" -s -S | python -c "import sys,json;print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"

# /ask
$q = [System.Uri]::EscapeDataString($Query)
$url = "$BaseUrl/ask?q=$q&lang=$Lang"
Write-Host "`n[2] GET /ask"
if ($API_TOKEN) {
  curl.exe --get $url -H "x-api-key: $API_TOKEN" -s -S | python -c "import sys,json;print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"
} else {
  curl.exe --get $url -s -S | python -c "import sys,json;print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"
}

# /feedback
Write-Host "`n[3] POST /feedback"
$body = @{
  q = $Query
  answer = ""
  label = "comment"
  note = "smoke"
  sources = @()
} | ConvertTo-Json -Depth 4 -Compress

if ($API_TOKEN) {
  curl.exe -X POST "$BaseUrl/feedback" -H "Content-Type: application/json" -H "x-api-key: $API_TOKEN" -d "$body" -s -S ^
    | python -c "import sys,json;print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"
} else {
  curl.exe -X POST "$BaseUrl/feedback" -H "Content-Type: application/json" -d "$body" -s -S ^
    | python -c "import sys,json;print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"
}

Write-Host "`nDone."
