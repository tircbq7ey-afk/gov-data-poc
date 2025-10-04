# batch_ask.ps1  --  CSV一括質問 → answers.csv を取得
param(
  [string]$ApiBase = "http://127.0.0.1:8010",
  [string]$CsvPath = ".\sample.csv",
  [int]$TopK = 5,
  [double]$MinScore = 0.0,
  [string]$Out = ".\answers.csv"
)

if (-not (Test-Path $CsvPath)) { Write-Error "CSV が見つかりません: $CsvPath"; exit 1 }

try {
  $url = "$ApiBase/batch-ask?top_k=$TopK&min_score=$([cultureinfo]::InvariantCulture.NumberFormat.NumberDecimalSeparator -replace ',', '.')$MinScore"
  Invoke-WebRequest -Method Post -Uri $url -Form @{ file = Get-Item $CsvPath } -OutFile $Out
  Write-Host "OK: $Out を作成しました。" -ForegroundColor Green
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
