param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string]$EnvFile = ".env",
  [string]$Lang    = "ja",
  [string]$Query   = "パスポート更新の手続きは？"
)

$ErrorActionPreference = "Stop"

# API TOKEN
$t = (Get-Content $EnvFile | Select-String '^API_TOKEN=').ToString().Split('=')[1].Trim()

Write-Host "== Health (app/proxy) =="
try {
  curl.exe "$BaseUrl/health" | Out-Host
} catch { Write-Warning $_.Exception.Message }

Write-Host "== /ask =="
$q = [uri]::EscapeDataString($Query)
curl.exe --get "$BaseUrl/ask" -H "x-api-key: $t" --data-urlencode "q=$q" --data-urlencode "lang=$Lang" | Out-Host

Write-Host "== /feedback =="
$fb = @{
  q       = 'test'
  answer  = 'ok'
  label   = 'good'
  sources = @('https://example.com/a', '/docs/b')
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$BaseUrl/feedback" `
  -Headers @{ 'x-api-key' = $t; 'Content-Type' = 'application/json' } `
  -Body $fb | Out-Host
