# fix_texts.py  -- data/db/texts.json を UTF-8(BOMなし)に直し、JSON配列か検証
from pathlib import Path
import json, sys

p = Path(r"C:\Users\yuji sato\gov-data-poc\data\db\texts.json")

# 1) ファイル存在チェック
if not p.exists():
    print(f"NG: ファイルが見つかりません -> {p}")
    sys.exit(1)

raw = p.read_bytes()

# 2) 先頭 BOM を除去
if raw[:3] == b'\xef\xbb\xbf':
    raw = raw[3:]

# 3) JSON として読み込み
try:
    data = json.loads(raw.decode("utf-8"))
except Exception as e:
    print("NG: JSON として読めません:", e)
    sys.exit(1)

# 4) 配列 [] であることを検証
if not isinstance(data, list):
    print("NG: texts.json は配列 (角括弧 [ ... ]) である必要があります。")
    sys.exit(1)

# 5) 最低限のキー確認（任意ですが早期発見に有効）
need = {"id", "title", "text"}
for i, item in enumerate(data):
    if not isinstance(item, dict) or not need.issubset(item.keys()):
        print(f"NG: {i} 行目のレコードが不正です。必要キー: {need}")
        sys.exit(1)

# 6) BOM なし UTF-8 で書き戻し（整形）
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK: 正常化完了。items={len(data)} を UTF-8(BOMなし) で保存しました。")
