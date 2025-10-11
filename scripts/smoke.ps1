param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string]$EnvFile = ".env",
  [string]$Lang = "ja",
  [string]$Query = "パスポート更新の手続きは？"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ApiTokenFromEnv($path) {
  if (!(Test-Path $path)) { return "" }
  $line = Get-Content -Raw -Encoding UTF8 $path |
    Select-String 'API_TOKEN\s*=' -SimpleMatch | Select-Object -First 1
  if ($null -eq $line) { return "" }
  return ($line.ToString().Split('=')[1]).Trim()
}

$TOKEN = Get-ApiTokenFromEnv $EnvFile
$Headers = @{}
if ($TOKEN -ne "") { $Headers["x-api-key"] = $TOKEN }

Write-Host "== Health =="
Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -Headers $Headers | Out-Host

$qEsc = [uri]::EscapeDataString($Query)
Write-Host "`n== Ask =="
Invoke-RestMethod -Method Get -Uri "$BaseUrl/ask?q=$qEsc&lang=$Lang" -Headers $Headers | Out-Host

Write-Host "`n== Feedback =="
$body = @{
  q       = $Query
  answer  = "ok"
  label   = "good"
  sources = @(@{source_id="manual"; score=1})
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$BaseUrl/feedback" -Headers ($Headers + @{ "Content-Type"="application/json" }) -Body $body | Out-Host

Write-Host "`nOK"
