import hashlib, json, os
from pathlib import Path

RAW_DIR = Path("data/raw")
HASH_FILE = Path("data/db/hashes.json")

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def detect_diffs():
    # 旧ハッシュを読み込み
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            old_hashes = json.load(f)
    else:
        old_hashes = {}

    diffs = []
    new_hashes = {}

    for file in RAW_DIR.glob("**/*.*"):
        h = file_hash(file)
        new_hashes[str(file)] = h
        if str(file) not in old_hashes or old_hashes[str(file)] != h:
            diffs.append(file)

    # 新しいハッシュを保存
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(new_hashes, f, ensure_ascii=False, indent=2)

    return diffs

if __name__ == "__main__":
    updated_files = detect_diffs()
    print("差分対象ファイル:", updated_files)
