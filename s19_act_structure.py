# -*- coding: utf-8 -*-
"""
S19：起承転結設計スキル
呼び出し：python run_pipeline.py --skill 19 --type short
役割：S14（全体プロット）とS18（伏線）を統合し、
     四幕構成を「章ごとの役割」として具体化する。
     どんでん返しから逆算した必然性のある章構成を設計する。

S14との違い：
  S14：物語全体の「構造」（何が起きるか）
  S19：各章の「役割・感情・伏線配置」（どう描くか）

次ステップ：S20（章プロット設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s19_act_structure"


# ============================================================
# 章構成テンプレート（novel_type別）
# ============================================================

CHAPTER_TEMPLATES = {
    "short": {
        "total": "プロローグ + 9〜10章 + エピローグ",
        "acts": [
            {"name": "プロローグ",    "range": "0〜2%",    "role": "認識反転の予告・冒頭フック"},
            {"name": "第1章",         "range": "3〜15%",   "role": "日常描写・欠落の提示・非日常突入"},
            {"name": "第2〜3章",      "range": "16〜35%",  "role": "承前半前半・問いの深化・伏線配置"},
            {"name": "第4〜5章",      "range": "36〜49%",  "role": "承前半後半・欠落が痛みになる"},
            {"name": "第5章最終",     "range": "50%",      "role": "ミッドポイント・目的の転換"},
            {"name": "第6〜7章",      "range": "51〜74%",  "role": "承後半・問いの答えが崩れ始める"},
            {"name": "第8章最終",     "range": "75%",      "role": "転・どんでん返し発生"},
            {"name": "第9〜10章",     "range": "76〜98%",  "role": "結・クライマックス・欠落との対峙"},
            {"name": "エピローグ",    "range": "99〜100%", "role": "余韻・認識反転の残像"},
        ],
    },
    "medium": {
        "total": "プロローグ + 12〜15章 + エピローグ",
        "acts": [
            {"name": "プロローグ",    "range": "0〜2%",    "role": "認識反転の予告・冒頭フック"},
            {"name": "第1〜2章",      "range": "3〜15%",   "role": "日常描写・欠落の提示・非日常突入"},
            {"name": "第3〜6章",      "range": "16〜49%",  "role": "承前半・問いの深化・伏線配置"},
            {"name": "第7章",         "range": "50%",      "role": "ミッドポイント・目的の転換"},
            {"name": "第8〜10章",     "range": "51〜74%",  "role": "承後半・問いの答えが崩れ始める"},
            {"name": "第11章",        "range": "75%",      "role": "転・どんでん返し発生"},
            {"name": "第12〜14章",    "range": "76〜98%",  "role": "結・クライマックス"},
            {"name": "エピローグ",    "range": "99〜100%", "role": "余韻"},
        ],
    },
    "long": {
        "total": "プロローグ + 13章（章定義は別途）+ エピローグ",
        "acts": [
            {"name": "プロローグ",    "range": "0〜2%",    "role": "認識反転の予告"},
            {"name": "第1章",         "range": "3〜14%",   "role": "起・日常と欠落"},
            {"name": "第1章最終",     "range": "15%",      "role": "非日常突入"},
            {"name": "第2〜5章",      "range": "16〜49%",  "role": "承前半"},
            {"name": "第5章最終",     "range": "50%",      "role": "ミッドポイント"},
            {"name": "第6〜8章",      "range": "51〜74%",  "role": "承後半"},
            {"name": "第8章最終",     "range": "75%",      "role": "転・どんでん返し"},
            {"name": "第9〜10章",     "range": "76〜98%",  "role": "結"},
            {"name": "エピローグ",    "range": "99〜100%", "role": "余韻"},
        ],
    },
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s8":  base / "s08_emotion"     / f"s08_emotion_latest_{novel_type}.md",
        "s14": base / "s14_plot_main"   / f"s14_plot_latest_{novel_type}.md",
        "s15": base / "s15_subplot"     / f"s15_subplot_latest_{novel_type}.md",
        "s18": base / "s18_foreshadow"  / f"s18_foreshadow_latest_{novel_type}.md",
    }
    limits = {"s8": 1500, "s14": 1500, "s15": 1500, "s18": 1500}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""

    return results


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(prev: dict, novel_type: str) -> str:

    template = CHAPTER_TEMPLATES.get(novel_type, CHAPTER_TEMPLATES["short"])
    acts_text = "\n".join(
        f"  {a['name']}（{a['range']}）：{a['role']}"
        for a in template["acts"]
    )

    return f"""あなたはこの小説作品の「章構成設計者」です。
S14（全体プロット）とS18（伏線）を統合し、
各章の「役割・感情・伏線配置・章末フック」を設計してください。

重要思想：
・各章は「欠落にどう作用するか」を持つ
・章末には必ず「次を読みたくなる疑問・引き」を仕込む
・どんでん返し（転）を最初に確定してから逆算で各章を設計する

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【章構成テンプレート（{novel_type}）】
全体構成：{template["total"]}
{acts_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S14 全体プロット設計（各幕の内容）】
{prev["s14"]}

【S18 伏線設計（配置タイムライン）】
{prev.get("s18_table") or prev["s18"]}

【S15 並行線設計（サブプロットの動き）】
{prev["s15"]}

【S8 感情波形（各フェーズの感情状態）】
{prev["s8"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 起承転結設計書（S19）

---

## ■ 章構成サマリー

| 章 | 位置 | 主な出来事 | 欠落への作用 | 配置伏線 | 感情強度 |
|---|:---:|---------|-----------|--------|:------:|
| プロローグ | 0〜2% | | | | /10 |
| 第1章 | 3〜15% | | | | /10 |
| 第2〜3章 | 16〜35% | | | | /10 |
| 第4〜5章 | 36〜49% | | | | /10 |
| ミッドポイント | 50% | | | | /10 |
| 第6〜7章 | 51〜74% | | | | /10 |
| 転 | 75% | | | | /10 |
| 第9〜10章 | 76〜98% | | | | /10 |
| エピローグ | 99〜100% | | | | /10 |

---

## ■ プロローグの設計

**役割：** 認識反転の予告・冒頭フック
**冒頭1文：**（S14で確定した案を転記）
**プロローグで提示する内容：**
**仕込む伏線ID：**（S18の伏線テーブルから）
**感情強度：** /10
**章末フック：**（なし・または読者を引き込む疑問）

---

## ■ 第1章の設計【起・非日常突入】

**役割：** 日常描写・欠落の提示・非日常突入（15%）
**日常パートで描くこと：**
**欠落の「見え方」（読者には見えるが主人公は気づかない）：**
**非日常突入のきっかけ：**
**仕込む伏線ID：**
**感情強度：** /10
**章末フック：**（読者が次を読まずにいられない疑問）

---

## ■ 第2〜3章の設計【承前半前半】

**役割：** 問いの深化・伏線配置
**この幕で深まる問い：**
**並行線の動き：**（相方・サブキャラの動き）
**仕込む伏線ID：**
**感情強度：** /10
**章末フック：**

---

## ■ 第4〜5章の設計【承前半後半】

**役割：** 欠落が初めて「痛み」になる
**欠落が痛みになる具体的な場面：**
**主人公が「答え」を誤解していることが最も際立つ瞬間：**
**仕込む伏線ID：**
**感情強度：** /10
**章末フック：**（ミッドポイント直前の最大緊張）

---

## ■ ミッドポイント（第5章最終）の設計

**役割：** 主人公の目的が変化する
**目的が変化するきっかけ：**
**転換前の目的 → 転換後の目的：**
**感情状態：**（S8の感情波形と合わせて）
**感情強度：** /10
**章末フック：**

---

## ■ 第6〜7章の設計【承後半】

**役割：** 問いの答えが崩れ始める
**崩れ始めるもの（信念・関係・前提）：**
**読者が「何かがおかしい」と感じ始める描写：**
**転への準備として積み上げるもの：**
**並行線の収束・交差：**
**仕込む伏線ID：**
**感情強度：** /10
**章末フック：**（転直前の最高の緊張）

---

## ■ 転・第8章最終の設計【どんでん返し】

**役割：** どんでん返し発生
**どんでん返しの瞬間：**（S14から転記）
**この瞬間に回収される伏線ID：**
**主人公の「問いへの答え」の書き換わり：**
**感情強度：** /10（最高点に近い）
**章末フック：**（どん底へ落下する予告）

---

## ■ 第9〜10章の設計【結・クライマックス】

**役割：** どん底から再起・欠落との対峙
**どん底からの再起きっかけ：**
**クライマックスの場面：**
**欠落と向き合う最後の選択：**
**感情強度：** /10（最高点）
**最終回収される伏線ID：**
**章末フック：**（なし・または余韻）

---

## ■ エピローグの設計

**役割：** 余韻・認識反転の残像
**最後の場面：**
**S8読後感との接続：**
**最後の1文：**（S14から転記）
**感情強度：** /10
**「プロローグを振り返ると何が見えるか」：**

---

## ■ S20（章プロット設計）への引き渡しパラメータ

**最優先で詳細設計すべき章：**（どんでん返しに最も重要な章）
**各章の文字数目安（{novel_type}）：**
**章ごとの視点人物（必要な場合）：**
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token      = config["api_keys"]["notion_token"]
    plot_db    = config["notion_dbs"].get("plot_db", "")
    novel_type = config.get("novel_type", "short")
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")

    template = CHAPTER_TEMPLATES.get(novel_type, CHAPTER_TEMPLATES["short"])
    print("\n[S19] 起承転結設計スキル 開始")
    print(f"  小説タイプ: {novel_type}（{template['total']}）")

    prev = load_prev_outputs(novel_type)

    # fix①: S18のS19引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s18_path = _Path(__file__).parent.parent / "output" / "s18_foreshadow" \
               / f"s18_foreshadow_latest_{novel_type}.md"
    if _s18_path.exists():
        _s18_full = _s18_path.read_text(encoding="utf-8")
        _idx = _s18_full.rfind("## ■ S19（起承転結設計）への引き渡しパラメータ")
        prev["s18_table"] = _s18_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s18_table"] = ""

    prompt = build_prompt(prev, novel_type)
    print("  起承転結設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 起承転結設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s19_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s19_act_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_起承転結設計")},
            "スキル":     {"rich_text": txt("S19_起承転結設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "起承転結設計", result)

    print("[S19] 完了\n")
    if novel_type == "long":
        print("  次のステップ: S20（章プロット設計・long専用）")
        print("  コマンド例: python run_pipeline.py --skill 20 --type long")
    else:
        print(f"  次のステップ: S21（余白設計）※S20はlong専用のためスキップ")
        print(f"  コマンド例: python run_pipeline.py --skill 21 --type {novel_type}")

    return {"result": result, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"] = args.type
    run(config=_config)
