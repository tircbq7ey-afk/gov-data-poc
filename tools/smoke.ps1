<# 
  tools/smoke.ps1
  - API疎通（/health）
  - /ask（日本語/ベトナム語 各1問）
  - /feedback POST（JSON）とコンテナ内JSONL保存確認
  失敗時は非ゼロ終了。PowerShell 7 推奨。
#>

param(
  [string]$Base = "http://127.0.0.1:8080",
  [string]$ApiKey = $env:API_TOKEN,
  [string]$Compose = "docker-compose.prod.yml",
  [switch]$VerboseHttp
)

if (-not $ApiKey) {
  Write-Error "APIトークンがありません。環境変数 API_TOKEN を設定してください。"
  exit 10
}

$headers = @{ "x-api-key" = $ApiKey }

function Invoke-JsonPost {
  param(
    [string]$Url,
    [hashtable]$Body
  )
  $json = $Body | ConvertTo-Json -Depth 8 -Compress
  if ($VerboseHttp) { Write-Host "POST $Url`n$json" -ForegroundColor DarkGray }
  return Invoke-RestMethod -Method POST -Uri $Url -Headers $headers -ContentType "application/json" -Body $json
}

$ok = $true

# 1) /health
try {
  $h = Invoke-RestMethod -Method GET -Uri "$Base/health"
  Write-Host "Health: $($h)" -ForegroundColor Green
} catch {
  Write-Host "Health: 失敗 $_" -ForegroundColor Red
  $ok = $false
}

# 2) /ask（日本語）
try {
  $resJa = Invoke-JsonPost -Url "$Base/ask" -Body @{ lang="ja"; q="パスポート更新の手続きは？" }
  Write-Host "ASK(jp): OK`n$($resJa | ConvertTo-Json -Depth 8)" -ForegroundColor Green
} catch {
  Write-Host "ASK(jp): 失敗 $_" -ForegroundColor Red
  $ok = $false
}

# 3) /ask（ベトナム語）
try {
  $resVi = Invoke-JsonPost -Url "$Base/ask" -Body @{ lang="vi"; q="Thẻ tạm trú là gì?" }
  Write-Host "ASK(vi): OK`n$($resVi | ConvertTo-Json -Depth 8)" -ForegroundColor Green
} catch {
  Write-Host "ASK(vi): 失敗 $_" -ForegroundColor Red
  $ok = $false
}

# 4) /feedback（JSON保存）
try {
  $fb = @{
    q       = "test"
    answer  = "ok"
    label   = "good"
    sources = @("https://example.com/a", "/docs/b")
  }
  $fbRes = Invoke-JsonPost -Url "$Base/feedback" -Body $fb
  Write-Host "Feedback POST: OK`n$($fbRes | ConvertTo-Json -Depth 8)" -ForegroundColor Green
} catch {
  Write-Host "Feedback POST: 失敗 $_" -ForegroundColor Red
  $ok = $false
}

# 5) コンテナ内 JSONL 末尾行チェック
try {
  $cmd = "ls -1 /data/feedback 2>/dev/null | tail -n1 | xargs -I{} sh -lc 'tail -n1 /data/feedback/{}'"
  $out = & docker compose -f $Compose exec -T app sh -lc $cmd
  if ($LASTEXITCODE -ne 0 -or -not $out) { throw "feedbackファイルが見つからない/読めない" }
  Write-Host "Feedback JSONL tail: $out" -ForegroundColor Green
} catch {
  Write-Host "Feedback JSONL確認: 失敗 $_" -ForegroundColor Red
  $ok = $false
}

if (-not $ok) { exit 1 } else { exit 0 }
