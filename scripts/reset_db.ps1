param()

$proj = "C:\Users\yuji sato\gov-data-poc"
Set-Location $proj
.\.venv\Scripts\Activate.ps1

$env:EMBED_MODEL = 'text-embedding-3-small'
$env:EMBED_DIM   = '1536'

Remove-Item -Recurse -Force .\data\db\* -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force .\data\db | Out-Null

$json = @'
[
  {
    "id": "visa-docs-001",
    "title": "就労ビザ申請に必要な書類",
    "text": "就労ビザの申請には、在留資格認定証明書交付申請書、雇用契約書、履歴書、会社概要、源泉徴収票 などが必要です。",
    "source_url": "https://example.go.jp/visa",
    "source_path": "local-manual"
  }
]
'@
$dst = Join-Path $PWD "data\db\texts.json"
[System.IO.File]::WriteAllText($dst, $json, [System.Text.UTF8Encoding]::new($false))

Get-Content $dst -Raw | ConvertFrom-Json | Out-Null

python .\build_index.py
python .\verify_db.py
