# rebuild_all.ps1
# 実行例: powershell -ExecutionPolicy Bypass -File .\rebuild_all.ps1
Write-Host "== clean db =="
Remove-Item -Force -Recurse .\data\db\* -ErrorAction SilentlyContinue | Out-Null

Write-Host "== parse =="
python .\parse.py

Write-Host "== embed =="
python .\embed.py

Write-Host "== verify =="
python .\verify_db.py
