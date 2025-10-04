# scripts/stop_api.ps1
param([int]$Port = 8010)

# ポート 8010 をLISTENしているPIDを止める
$pid = (netstat -ano | Select-String ":$Port\s+LISTENING").ToString().Split()[-1]
if ($pid) {
  try { Stop-Process -Id [int]$pid -Force; "stopped pid $pid" }
  catch { "no process or already stopped" }
} else {
  "no listener on :$Port"
}
