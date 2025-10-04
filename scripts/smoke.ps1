# smoke.ps1 - Windows PowerShell用スモーク（ベトナム語FAQで検証）
param([switch]$NoBuild)
$ErrorActionPreference = "Stop"

function Curl($url) { & curl.exe -sS $url }

Write-Host "== Compose up =="
if (-not $NoBuild) {
  docker compose -f docker-compose.prod.yml up -d --build
} else {
  docker compose -f docker-compose.prod.yml up -d
}
Start-Sleep -Seconds 4

Write-Host "`n== Health (app/proxy) =="
Curl http://127.0.0.1:8010/health | Out-Host
Curl http://127.0.0.1:8080/health | Out-Host

Write-Host "`n== ASK (vi: hit / miss) =="
$API="http://127.0.0.1:8080"
$H=@{"x-api-key"="changeme-local-token"} # .env の API_TOKEN に合わせて変更
# hit（faq_vi.json にある質問）
& curl.exe -sS -H "x-api-key: $($H['x-api-key'])" "$API/ask?lang=vi&q=Khi%20n%C3%A0o%20t%C3%B4i%20c%C3%B3%20th%E1%BB%83%20n%E1%BB%99p%20%C4%91%C6%A1n%20gia%20h%E1%BA%A1n%20t%C6%B0%20c%C3%A1ch%20l%C6%B0u%20tr%C3%BA%3F" | Out-Host
# miss
& curl.exe -sS -H "x-api-key: $($H['x-api-key'])" "$API/ask?lang=vi&q=C%C3%A2u%20h%E1%BB%8Fi%20kh%C3%B4ng%20c%C3%B3" | Out-Host

Write-Host "`n== Feedback (JSONL) =="
$body = '{"q":"Khi nào nộp gia hạn?","answer":"Trong 3 tháng trước hạn.","label":"good","sources":["https://www.moj.go.jp/isa/"]}'
& curl.exe -sS -H "Content-Type: application/json" -H "x-api-key: $($H['x-api-key'])" -X POST -d $body "$API/feedback" | Out-Host

Write-Host "`n== Done =="
