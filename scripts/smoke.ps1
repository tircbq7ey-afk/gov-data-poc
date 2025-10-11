Param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string]$EnvFile = ".env",
  [string]$Lang = "ja",
  [string]$Query = "パスポート更新の手続きは？"
)

Write-Host "== Health check =="
try {
  curl.exe --get "$BaseUrl/health" | Out-Host
} catch { Write-Error $_; }

# .env から API_TOKEN を読む
$token = (Get-Content $EnvFile | Select-String '^API_TOKEN=').ToString().Split('=')[1].Trim()

Write-Host "== /ask =="
$resp = curl.exe --get "$BaseUrl/ask" -H "x-api-key: $token" --data-urlencode "q=$Query" --data-urlencode "lang=$Lang"
$resp | Out-Host

Write-Host "== /feedback =="
$body = @{
  q = "test"
  answer = "ok"
  label = "good"
  sources = @("https://example.com/a","/docs/b")
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "$BaseUrl/feedback" `
  -Headers @{ "x-api-key" = $token; "Content-Type"="application/json" } `
  -Body $body | Out-Host
