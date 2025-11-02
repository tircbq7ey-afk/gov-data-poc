param(
  [int]$Port = 8010,
  [switch]$Open,
  [switch]$Tail,
  [switch]$Kill
)

$ErrorActionPreference = "Stop"

# --- path check ---
$root = Split-Path -Parent $PSCommandPath
$py   = Join-Path $root ".\.venv\Scripts\python.exe"
$api  = Join-Path $root "qa_service.py"

if (!(Test-Path $py))  { throw "venv の Python が見つかりません: $py" }
if (!(Test-Path $api)) { throw "qa_service.py が見つかりません: $api" }

# --- logs ---
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "qa_service.out.log"
$errLog = Join-Path $logDir "qa_service.err.log"

# --- 同ポートの既存プロセスを停止（任意） ---
if ($Kill) {
  $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($c) {
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p) {
      Write-Host ("kill PID {0} using :{1}" -f $p.Id, $Port) -ForegroundColor Yellow
      Stop-Process -Id $p.Id -Force
      Start-Sleep -Milliseconds 500
    }
  }
}

# --- 起動 ---
$env:PORT = "$Port"   # qa_service.py 側で PORT を読む
Write-Host ("=== starting qa_service.py on http://127.0.0.1:{0} ===" -f $Port) -ForegroundColor Cyan
$sp = Start-Process -FilePath $py -ArgumentList @($api) -WorkingDirectory $root `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
        -PassThru -WindowStyle Hidden

Write-Host ("qa_service started (PID={0})" -f $sp.Id) -ForegroundColor Green
Write-Host ("out: {0}`nerr: {1}" -f $outLog, $errLog)

# --- ヘルスチェック ---
$ping = "http://127.0.0.1:$Port/ping"
$ok = $false
for ($i=0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 400
  try {
    $r = Invoke-RestMethod -Uri $ping -TimeoutSec 2
    if ($r.ok) { $ok = $true; break }
  } catch {}
}
if ($ok) { Write-Host ("API health: OK ({0})" -f $ping) -ForegroundColor Green }
else {    Write-Host ("API health: NG ({0}) → ログを確認: {1}" -f $ping, $outLog) -ForegroundColor Red }

# --- ブラウザ/ログ ---
if ($Open) { Start-Process "http://127.0.0.1:$Port/index.html" }
if ($Tail) {
  Write-Host ("---- tail -f {0} (Ctrl+C で終了) ----" -f $outLog) -ForegroundColor DarkGray
  Get-Content $outLog -Tail 100 -Wait
}

return $sp.Id
