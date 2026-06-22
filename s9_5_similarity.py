# -*- coding: utf-8 -*-
"""
S9_5：類似性チェックスキル
呼び出し：python run_pipeline.py --skill 95 --type short
挿入位置：S9完了後・S10開始前

処理フロー：
  ① S1〜S9の出力からキーワードを抽出
  ② Webで類似作品を検索（duckduckgo-search）
  ③ GPT-5.5 xhighで類似度を分析
  ④ レポートを出力（類似度・差別化ポイント・修正提案）

インストール：pip install ddgs
"""

import sys
import json
import time
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s9_5_similarity"


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_design_summary(novel_type: str) -> dict:
    """S1〜S9の設計サマリーを収集する"""
    base = Path(__file__).parent.parent / "output"
    paths = {
        "s1":  base / "s01_plot_twist"   / f"s01_twist_latest_{novel_type}.md",
        "s5":  base / "s05_gender_design" / f"s05_gender_latest_{novel_type}.md",
        "s6":  base / "s06_gravity"       / f"s06_gravity_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"    / f"s07_philosophy_latest_{novel_type}.md",
        "s8":  base / "s08_emotion"       / f"s08_emotion_latest_{novel_type}.md",
        "s9":  base / "s09_theme"         / f"s09_theme_latest_{novel_type}.md",
    }
    limits = {"s1": 800, "s5": 600, "s6": 600, "s7": 1000, "s8": 600, "s9": 800}

    result = {}
    for key, path in paths.items():
        if path.exists():
            text = path.read_text(encoding="utf-8")[:limits[key]]
            result[key] = text
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            result[key] = ""
    return result


# ============================================================
# キーワード生成（GPT-5.5）
# ============================================================

def generate_search_keywords(design: dict, config: dict) -> list:
    """S1〜S9の設計から検索キーワードを生成"""
    prompt = f"""以下の小説設計書から、類似作品を検索するためのキーワードを生成してください。

【設計情報】
S1（どんでん返し）:
{design.get('s1', '')}

S7（哲学的問い）:
{design.get('s7', '')}

S9（テーマ）:
{design.get('s9', '')}

S6（関係性重力）:
{design.get('s6', '')}

S5（ペアリング・熱量）:
{design.get('s5', '')}

【出力形式】
以下のJSON形式のみで出力してください（前置き不要）：
{{
  "queries": [
    "検索クエリ1（日本語小説ジャンル・設定・テーマ）",
    "検索クエリ2（英語での類似作品検索）",
    "検索クエリ3（キャラクター設定・関係性）",
    "検索クエリ4（どんでん返し・テーマの類似作品）",
    "検索クエリ5（具体的な作品名・シリーズ）"
  ],
  "core_concept": "この作品の核心を1文で表現",
  "genre_tags": ["ジャンルタグ1", "ジャンルタグ2", "ジャンルタグ3"]
}}
"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from openai_utils import call_openai_thinking
        model  = config.get("openai_model", "o3")
        effort = config.get("reasoning_effort", "medium")
        result = call_openai_thinking(
            prompt, model=model,
            reasoning_effort=effort,
            max_tokens=2000
        )
    except Exception:
        result = call_claude_sonnet(prompt)

    try:
        # JSON部分を抽出
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except Exception:
        pass

    # フォールバック（設計情報からの自動抽出に失敗した場合）
    return {
        "queries": [
            "小説 あらすじ 似た作品 探し方",
            "how to find novels with a similar premise",
            "物語 設定 似ている 作品 一覧",
            "小説 テーマ 近い 作品 おすすめ",
            "books with similar themes and story structure"
        ],
        "core_concept": "ある人物が出来事をきっかけに変わっていく物語",
        "genre_tags": ["小説", "物語", "フィクション"]
    }


# ============================================================
# Web検索（DuckDuckGo）
# ============================================================

def web_search_similar_works(queries: list) -> list:
    """DuckDuckGoで類似作品を検索する"""
    try:
        from ddgs import DDGS
    except ImportError:
        print("  [WARN] duckduckgo-search未インストール")
        print("         pip install ddgs")
        return []

    all_results = []
    ddgs = DDGS()

    for query in queries[:5]:
        print(f"    検索: {query[:50]}...")
        try:
            results = list(ddgs.text(
                query,
                max_results=5,
                region="jp-jp",
            ))
            for r in results:
                all_results.append({
                    "title": r.get("title", ""),
                    "body":  r.get("body", "")[:200],
                    "url":   r.get("href", ""),
                    "query": query,
                })
            time.sleep(0.5)  # レート制限対策
        except Exception as e:
            print(f"    [WARN] 検索エラー: {e}")
            continue

    print(f"  [INFO] 検索結果: {len(all_results)}件")
    return all_results


# ============================================================
# 類似度分析（GPT-5.5 Thinking）
# ============================================================

def analyze_similarity(design: dict, search_results: list,
                        keywords: dict, config: dict) -> str:
    """GPT-5.5 xhighで類似度を分析する"""

    results_text = "\n".join([
        f"・{r['title']}: {r['body']}"
        for r in search_results[:20]
    ]) or "（Web検索結果なし）"

    prompt = f"""あなたはこの小説作品の「類似性チェッカー」です。
以下の設計情報と検索結果を元に、類似性を分析してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【この作品の核心コンセプト】
{keywords.get('core_concept', '')}

【ジャンルタグ】
{', '.join(keywords.get('genre_tags', []))}

【S7 哲学的問い（核心）】
{design.get('s7', '')}

【S9 テーマ設計】
{design.get('s9', '')}

【S1 どんでん返し設計】
{design.get('s1', '')}

【S6 関係性重力】
{design.get('s6', '')}

【Web検索で見つかった関連作品・情報】
{results_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式でレポートを出力してください：

---

## ■ 類似性チェック総評

**総合類似度判定：** 低／中／高
**判定理由：**

---

## ■ 類似が疑われる作品リスト

| 作品名 | 類似している要素 | 類似度 | 要注意度 |
|------|-------------|:----:|:------:|
| | | %  | 🔴/🟡/🟢 |

---

## ■ 類似要素の詳細分析

### 🔴 要注意（修正を検討すべき類似点）
（なければ「なし」）

### 🟡 要確認（差別化が必要な要素）

### 🟢 問題なし（十分差別化されている要素）

---

## ■ この作品の独自性・強み

**他作品にない独自要素（3〜5点）：**

---

## ■ 差別化のための修正提案

**S1（どんでん返し）の調整案：**（必要な場合のみ）
**S7（哲学的問い）の調整案：**（必要な場合のみ）
**S9（テーマ）の調整案：**（必要な場合のみ）
**設定・世界観の調整案：**（必要な場合のみ）

修正不要の場合：「現状の設計で差別化は十分です」

---

## ■ 次のステップ（S10開始前の確認事項）

🔴 要修正がある場合 → 修正後にS10を開始
🟡 要確認がある場合 → 確認後にS10を開始
🟢 問題なし → S10を開始してください
"""

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from openai_utils import call_openai_thinking
        model  = config.get("openai_model", "o3")
        effort = config.get("reasoning_effort", "high")
        print(f"  [分析] GPT-5.5 {effort}モードで類似度分析中...")
        result = call_openai_thinking(
            prompt, model=model,
            reasoning_effort=effort,
            max_tokens=8000
        )
        if result and len(result.strip()) > 100:
            return result
    except Exception as e:
        print(f"  [WARN] GPT-5.5エラー: {e} → Claude Sonnetにフォールバック")

    return call_claude_sonnet(prompt)


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

    print("\n[S9_5] 類似性チェックスキル 開始（S9.5）")
    print(f"  小説タイプ: {novel_type}")
    print(f"  処理: キーワード生成 → Web検索 → GPT-5.5分析")

    # ── S1〜S9 設計サマリーを読み込み ────────────
    design = load_design_summary(novel_type)

    # ── ① キーワード生成 ──────────────────────────
    print("\n  ① キーワード生成中...")
    keywords = generate_search_keywords(design, config)
    print(f"  核心コンセプト: {keywords.get('core_concept', '')[:60]}")
    print(f"  ジャンル: {', '.join(keywords.get('genre_tags', []))}")
    print(f"  検索クエリ: {len(keywords.get('queries', []))}件")

    # ── ② Web検索 ────────────────────────────────
    print("\n  ② Web検索中...")
    search_results = web_search_similar_works(keywords.get("queries", []))

    # ── ③ GPT-5.5で類似度分析 ─────────────────────
    print("\n  ③ 類似度分析中...")
    report = analyze_similarity(design, search_results, keywords, config)

    # ── 出力ファイル作成 ────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 検索結果の保存
    search_data = {
        "timestamp": timestamp,
        "keywords":  keywords,
        "results":   search_results,
    }
    search_path = OUTPUT_DIR / f"s9_5_{novel_type}_search_{timestamp}.json"
    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(search_data, f, ensure_ascii=False, indent=2)

    # レポートの保存
    content = f"""# 類似性チェックレポート（S9.5）
実行日時：{timestamp}
小説タイプ：{novel_type}
核心コンセプト：{keywords.get('core_concept', '')}
ジャンルタグ：{', '.join(keywords.get('genre_tags', []))}
検索件数：{len(search_results)}件

---

{report}
"""
    filepath = OUTPUT_DIR / f"s9_5_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s9_5_similarity_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_類似性チェック")},
            "スキル":     {"rich_text": txt("S9_5_類似性チェック")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "類似性チェックレポート", report)

    print("[S9_5] 完了\n")
    print("  🔴 要修正あり → S1〜S9を調整してから S10 へ")
    print("  🟡 要確認あり → 確認後に S10 へ")
    print("  🟢 問題なし  → S10 を開始してください")
    print(f"\n  コマンド例: python run_pipeline.py --skill 10 --type {novel_type}")

    return {"report": report, "keywords": keywords, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--reasoning-effort", default="high",
                        choices=["none", "low", "medium", "high", "xhigh"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"]       = args.type
    _config["reasoning_effort"] = args.reasoning_effort
    run(config=_config)
