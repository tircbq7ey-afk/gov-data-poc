param(
  [string]$Model = "text-embedding-3-small",
  [int]$Dim = 1536
)

$ErrorActionPreference = "Stop"
chcp 65001 > $null
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Set-Location "$PSScriptRoot\.."

# 1) texts.json の健全性チェック（BOM/配列形）
$path = ".\data\db\texts.json"
if (-not (Test-Path $path)) { throw "texts.json がありません: $path" }
$raw = Get-Content $path -Raw
try { $json = $raw | ConvertFrom-Json } catch { throw "texts.json が壊れています: $($_.Exception.Message)" }
if ($json.GetType().Name -ne 'Object[]') { throw "texts.json は **配列** である必要があります。" }

# 2) 既存DB削除
Remove-Item .\data\db\* -Force -ErrorAction SilentlyContinue

# 3) 環境変数セット
$env:EMBED_MODEL = $Model
$env:EMBED_DIM   = "$Dim"

# 4) 再構築
python .\build_index.py

# 5) 検証
python .\verify_db.py

Write-Host "`n== RESET OK =="
