# -*- coding: utf-8 -*-
"""
NOVEL_AUTOMATION 共通ユーティリティ
全スキルから呼び出す通信関数
"""

import os
import time
import yaml
import requests
import anthropic
from openai import OpenAI
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "common" / "config.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ============================================================
# API呼び出し
# ============================================================

def call_chatgpt(prompt: str, config: dict, retries: int = 3) -> str:
    """ChatGPT o3 呼び出し（発散・絞り込み・タイトル生成用）"""
    api_key = config["api_keys"]["openai"]
    client = OpenAI(api_key=api_key)
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=config["models"]["chatgpt_think"],
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=3000,
            )
            return response.choices[0].message.content
        except Exception as e:
            wait = 30 * (attempt + 1)
            print(f"  [WARNING] ChatGPT error: {e}. Retry in {wait}s ({attempt+1}/{retries})")
            time.sleep(wait)
    raise RuntimeError("ChatGPT API error persists.")

def call_claude_haiku(prompt: str, retries: int = 5) -> str:
    """Claude Haiku 呼び出し（キャラ設定・あらすじ用）"""
    client = anthropic.Anthropic()
    for attempt in range(retries):
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"  [WARNING] Claude rate limit. Retry in {wait}s")
            time.sleep(wait)
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"  [WARNING] Claude error: {e}. Retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Claude API error persists.")

def call_claude_sonnet(prompt: str, retries: int = 5) -> str:
    """Claude Sonnet 呼び出し（トラウマ設定・プロット用）"""
    client = anthropic.Anthropic()
    for attempt in range(retries):
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"  [WARNING] Claude rate limit. Retry in {wait}s")
            time.sleep(wait)
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"  [WARNING] Claude error: {e}. Retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Claude Sonnet API error persists.")

# ============================================================
# Notion操作
# ============================================================

NOTION_VERSION = "2022-06-28"

def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def txt(s: str) -> list:
    return [{"text": {"content": str(s)[:2000]}}]

def notion_create_page(token: str, db_id: str, properties: dict, children: list) -> str:
    """Notionにページを作成してページIDを返す"""
    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": children,
    }
    r = requests.post("https://api.notion.com/v1/pages",
                      headers=notion_headers(token), json=body)
    if r.status_code == 200:
        page_id = r.json().get("id", "")
        print(f"  [OK] Notion saved: {page_id}")
        return page_id
    else:
        print(f"  [WARNING] Notion error: {r.status_code} {r.text[:300]}")
        return ""

def notion_get_latest_idea(token: str, db_id: str) -> dict:
    """アイデアDBから最新の未使用レコードを取得"""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    body = {
        "filter": {"property": "ステータス", "select": {"equals": "未使用"}},
        "sorts": [{"property": "Name", "direction": "descending"}],
        "page_size": 1,
    }
    r = requests.post(url, headers=notion_headers(token), json=body)
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            return results[0]
    return {}

def notion_update_status(token: str, page_id: str, status: str):
    """ページのステータスを更新"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    body = {"properties": {"ステータス": {"select": {"name": status}}}}
    requests.patch(url, headers=notion_headers(token), json=body)

def notion_get_page_content(token: str, page_id: str) -> str:
    """ページのブロックコンテンツを取得してテキストに変換"""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    r = requests.get(url, headers=notion_headers(token))
    if r.status_code != 200:
        return ""
    blocks = r.json().get("results", [])
    texts = []
    for block in blocks:
        btype = block.get("type", "")
        rich_text = block.get(btype, {}).get("rich_text", [])
        for rt in rich_text:
            texts.append(rt.get("text", {}).get("content", ""))
    return "\n".join(texts)

def notion_setup_db(token: str, db_id: str, extra_props: dict = None):
    """DBにプロパティを追加（既存は無視）"""
    base_props = {
        "グループ": {"rich_text": {}},
        "ステータス": {
            "select": {
                "options": [
                    {"name": "未使用", "color": "green"},
                    {"name": "使用済み", "color": "gray"},
                    {"name": "次回に入れる", "color": "yellow"},
                ]
            }
        },
    }
    if extra_props:
        base_props.update(extra_props)
    url = f"https://api.notion.com/v1/databases/{db_id}"
    requests.patch(url, headers=notion_headers(token), json={"properties": base_props})

# ============================================================
# ファイル保存
# ============================================================


def notion_create_page_long(token: str, db_id: str, properties: dict,
                             content_title: str, content: str) -> str:
    """Notionにページを作成し、長文コンテンツをブロックに分割して追加"""
    import requests as _req
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    # ページ作成
    body = {"parent": {"database_id": db_id}, "properties": properties}
    r = _req.post("https://api.notion.com/v1/pages", headers=headers, json=body)
    if r.status_code not in (200, 201):
        print(f"  [ERROR] Notion page creation failed: {r.status_code}")
        return ""
    page_id = r.json().get("id", "")
    if not page_id:
        return ""

    # コンテンツをブロックに分割して追加（2000文字ずつ）
    MAX_BLOCK = 2000
    lines = content.split("\n")
    blocks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > MAX_BLOCK:
            if current:
                blocks.append({"object": "block", "type": "paragraph",
                                "paragraph": {"rich_text": [{"type": "text", "text": {"content": current}}]}})
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        blocks.append({"object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": current}}]}})

    # ブロックを100個ずつに分けて追加
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i+100]
        r2 = _req.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=headers,
            json={"children": chunk}
        )
        if r2.status_code not in (200, 201):
            print(f"  [ERROR] Notion blocks append failed: {r2.status_code}")
    total_chars = sum(len(b["paragraph"]["rich_text"][0]["text"]["content"]) for b in blocks)
    print(f"  [OK] Notion blocks appended: {len(blocks)}ブロック ({total_chars}文字)")
    return page_id


def save_output(skill_name: str, content: str, output_dir: Path) -> Path:
    """スキルの出力をファイルに保存"""
    output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"{skill_name}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath}")
    return filepath
