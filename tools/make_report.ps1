[CmdletBinding()]
param(
  [string]$Service = "app",
  [string]$ContainerPath = "/app/logs",
  [switch]$RunCharts
)

# --- 1) container id
$cid = (& docker compose ps -q $Service).Trim()
if (-not $cid) { Write-Error "container id not found (service: $Service)"; exit 1 }

# --- 2) output dirs
$stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$dstRoot = Join-Path -Path $PWD -ChildPath "logs_from_container"
$dst     = Join-Path -Path $dstRoot -ChildPath $stamp
New-Item -ItemType Directory -Force -Path $dst | Out-Null

# --- 3) copy logs (copy contents of /app/logs into $dst)
$srcSpec = "$($cid):$ContainerPath/."
Write-Host ">> docker cp $srcSpec  ->  $dst"
& docker cp $srcSpec $dst
if ($LASTEXITCODE -ne 0) { throw "docker cp failed." }

# --- 4) charts (optional)
if ($RunCharts) {
  $chartsOut = Join-Path -Path $PWD -ChildPath "reports\charts"
  New-Item -ItemType Directory -Force -Path $chartsOut | Out-Null

  $csvList = Get-ChildItem -Path $dst -Filter *.csv -File -ErrorAction SilentlyContinue
  if (-not $csvList) {
    Write-Host "no CSV found under: $dst  (charts are skipped)"
  }
  else {
    # resolve python
    $py = $null
    $cmd = Get-Command python  -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Path } else {
      $cmd = Get-Command python3 -ErrorAction SilentlyContinue
      if ($cmd) { $py = $cmd.Path }
    }
    if (-not $py) { throw "python not found on PATH." }

    # check CLI of feedback_report.py and call with the right args
    $helperOut = & $py "tools\feedback_report.py" "-h" 2>&1 | Out-String

    if ($helperOut -match "\-i.*INPUT_DIR" -and $helperOut -match "\-o.*OUT_DIR") {
      # your script style -> -i / -o
      Write-Host ">> feedback_report.py -i $dst -o $chartsOut"
      & $py "tools\feedback_report.py" "-i" $dst "-o" $chartsOut
    }
    elseif ($helperOut -match "--in_glob" -and $helperOut -match "--out_dir") {
      # older sample style -> --in_glob / --out_dir
      $inGlob = (Join-Path $dst "*.csv")
      Write-Host ">> feedback_report.py --in_glob $inGlob --out_dir $chartsOut"
      & $py "tools\feedback_report.py" "--in_glob" $inGlob "--out_dir" $chartsOut
    }
    else {
      throw "Unknown CLI of tools\feedback_report.py. Help was:`n$helperOut"
    }

    if ($LASTEXITCODE -ne 0) { throw "feedback_report.py failed." }
  }
}

Write-Host "All done. Logs -> $dst"
