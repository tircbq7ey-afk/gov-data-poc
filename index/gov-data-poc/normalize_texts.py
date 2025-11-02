# normalize_texts.py  ——  texts.json を必ず「配列のリスト」に直す
import json, os, pathlib
BASE = pathlib.Path(__file__).parent
DB = BASE / "data" / "db"
DB.mkdir(parents=True, exist_ok=True)

# 探す候補（どちらかにある想定）
candidates = [BASE / "texts.json", DB / "texts.json"]

src = next((p for p in candidates if p.exists()), None)
if not src:
    print("ERROR: texts.json が見つかりません（プロジェクト直下 or data/db）")
    raise SystemExit(1)

dst = DB / "texts.json"

def to_item(x, key=None):
    """色々な形を {text: "..."} 形式に寄せる"""
    if isinstance(x, str):
        return {"id": str(key) if key is not None else None, "text": x}

    if isinstance(x, dict):
        d = dict(x)
        # よくあるキー名の揺れを吸収
        for k in ("text", "body", "content", "本文"):
            if k in d and "text" not in d:
                d["text"] = d[k]
        if "text" not in d:
            # 文字列/数値の値をつなげて text を作る（最終手段）
            s = " ".join(str(v) for v in d.values() if isinstance(v, (str, int, float)))
            d["text"] = s
        if key is not None and "id" not in d:
            d["id"] = str(key)
        # 使いそうなメタは残す
        keep = {k: d[k] for k in ("url", "title", "source", "lang") if k in d}
        return {"id": d.get("id"), "text": d["text"], **keep}

    # それ以外はとりあえず文字列化
    return {"id": str(key) if key is not None else None, "text": str(x)}

with src.open("r", encoding="utf-8") as f:
    data = json.load(f)

items = []
if isinstance(data, list):
    items = [to_item(i) for i in data]
elif isinstance(data, dict):
    # { "items": [...] } / { "data": [...] } / { "id": {...}, ... } のどれでもOK
    if isinstance(data.get("items"), list):
        items = [to_item(i) for i in data["items"]]
    elif isinstance(data.get("data"), list):
        items = [to_item(i) for i in data["data"]]
    else:
        # 辞書のキーを id とみなす
        for k, v in data.items():
            items.append(to_item(v, key=k))
else:
    items = [to_item(data)]

# 空テキストは捨てる
items = [i for i in items if i.get("text")]

with dst.open("w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

print(f"OK: 正規化完了 {dst} に {len(items)} 件を書き込みました")
if items:
    print("例:", json.dumps(items[0], ensure_ascii=False)[:200])
