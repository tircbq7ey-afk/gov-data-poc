# quick_sheets_test.py
from __future__ import annotations
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime

# ★自分の値に変更
SPREADSHEET_ID = "1QHAXMsPTefKWAfO50rUqJ2HznqmWqM14Muo5W1YqEvQ"      # URLの /spreadsheets/d/ の次にある長い文字列
SHEET_RANGE     = "membership_events!A:G"  # シート名!範囲（7列）

# サービスアカウント鍵のパス（同じフォルダに置いた想定）
SA_KEY_PATH = "visa-subs-78c4be79a3c0.json"

def main():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SA_KEY_PATH, scopes=scopes)

    service = build("sheets", "v4", credentials=creds)
    sheets  = service.spreadsheets().values()

    # A:G の7列に入れる1行分のダミーデータ
    row = [
        datetime.utcnow().isoformat(timespec="seconds") + "Z",  # timestamp_utc
        "cus_demo123",     # customer_id
        "evt_demo123",     # event_id
        "invoice.payment_succeeded",  # event_type
        "active",          # status_after
        "user@example.com",# email
        "{}",              # metadata_json
    ]

    resp = sheets.append(
        spreadsheetId=SPREADSHEET_ID,
        range=SHEET_RANGE,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    updates = resp.get("updates", {})
    updated = updates.get("updatedCells")
    print("OK: appended 1 row, cells =", updated)

if __name__ == "__main__":
    main()
