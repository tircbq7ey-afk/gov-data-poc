param(
  [string]$Bind = '127.0.0.1',
  [int]   $Port = 8010
)

$ErrorActionPreference = 'Stop'

# プロジェクト直下へ
$proj = "C:\Users\yuji sato\gov-data-poc"
Set-Location $proj

# venv を有効化
$venv = Join-Path $proj ".venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }

# 依存を必要に応じてインストール（importlibは使わない）
$py = @'
import sys, subprocess

def missing(mod):
    try:
        __import__(mod)
        return False
    except Exception:
        return True

need = []
if missing("fastapi"):
    need.append("fastapi")
if missing("uvicorn"):
    need.append("uvicorn")
# python-multipart の import 名は "multipart"
if missing("multipart"):
    need.append("python-multipart")

if need:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *need])
'@
$py | python -   # PowerShell → Python (stdin) へ渡す

# すでに $Port をLISTENしているプロセスがあれば落とす
$listenPid = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty OwningProcess
if ($listenPid) {
  try { Stop-Process -Id $listenPid -Force -ErrorAction SilentlyContinue } catch {}
}

# 起動
$addr = "http://{0}:{1}" -f $Bind, $Port
Write-Host ("[start] {0}" -f $addr) -ForegroundColor Green
python -m uvicorn qa_service:app --host $Bind --port $Port --reload
