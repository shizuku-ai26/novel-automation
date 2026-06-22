# -*- coding: utf-8 -*-
"""
Notionの全DBにプロパティを一括セットアップするスクリプト
初回のみ実行してください
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import requests
import yaml

CONFIG_PATH = Path(__file__).parent / "common" / "config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

token = config["api_keys"]["notion_token"]
dbs = config["notion_dbs"]

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

props = {
    "スキル": {"rich_text": {}},
    "小説タイプ": {"rich_text": {}},
    "ステータス": {
        "select": {
            "options": [
                {"name": "未使用", "color": "green"},
                {"name": "使用済み", "color": "gray"},
                {"name": "お気に入り", "color": "yellow"},
            ]
        }
    },
}

for db_name, db_id in dbs.items():
    if not db_id or len(db_id) < 10:
        print(f"  スキップ（未設定）: {db_name}")
        continue
    r = requests.patch(
        f"https://api.notion.com/v1/databases/{db_id}",
        headers=headers,
        json={"properties": props}
    )
    if r.status_code == 200:
        print(f"  [OK] {db_name}: プロパティ設定完了")
    else:
        print(f"  [WARNING] {db_name}: {r.status_code} {r.text[:100]}")

print("\nセットアップ完了！")
