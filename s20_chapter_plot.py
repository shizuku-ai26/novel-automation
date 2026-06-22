# -*- coding: utf-8 -*-
"""
S20：章プロット設計スキル（長編専用）
呼び出し：python run_pipeline.py --skill 20 --type long
役割：長編小説の各章を「シーン単位」まで詳細設計する。
     短編・中編はS19→S21へ直接進む（S20をスキップ）。

長編専用の理由：
  短編・中編は章数が少なく、S19の章設計で十分。
  長編（10万字以上）は各章の「シーン構成」まで設計しないと
  執筆時に内容が散漫になりやすい。

設計対象：全章のシーン構成（1章あたり2〜4シーン）
次ステップ：S21（余白設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s20_chapter_plot"

# 長編の章定義（13章）
LONG_CHAPTERS = [
    {"order": 1,  "key": "ch8_final",  "name": "第8章最終",  "link": "転（75%）",        "position": "75%",      "volume": "全体の1%"},
    {"order": 2,  "key": "ch9",        "name": "第9章",      "link": "結前半（76〜85%）", "position": "76〜85%",  "volume": "全体の10%"},
    {"order": 3,  "key": "ch10",       "name": "第10章",     "link": "結後半（86〜98%）", "position": "86〜98%",  "volume": "全体の10〜15%"},
    {"order": 4,  "key": "epilogue",   "name": "エピローグ", "link": "エピローグ（99〜100%）", "position": "99〜100%", "volume": "全体の1〜2%"},
    {"order": 5,  "key": "ch5_final",  "name": "第5章最終",  "link": "ミッドポイント（50%）", "position": "50%",  "volume": "全体の2%"},
    {"order": 6,  "key": "ch6",        "name": "第6章",      "link": "承後半前半（51〜58%）", "position": "51〜58%", "volume": "全体の10%"},
    {"order": 7,  "key": "ch7",        "name": "第7章",      "link": "承後半中（59〜68%）", "position": "59〜68%",  "volume": "全体の10%"},
    {"order": 8,  "key": "ch8",        "name": "第8章（最終以外）", "link": "承後半後（69〜74%）", "position": "69〜74%", "volume": "全体の10%"},
    {"order": 9,  "key": "ch2",        "name": "第2章",      "link": "承前半前（16〜25%）", "position": "16〜25%",  "volume": "全体の10%"},
    {"order": 10, "key": "ch3",        "name": "第3章",      "link": "承前半中（26〜35%）", "position": "26〜35%",  "volume": "全体の10%"},
    {"order": 11, "key": "ch4",        "name": "第4章",      "link": "承前半後（36〜42%）", "position": "36〜42%",  "volume": "全体の5%"},
    {"order": 12, "key": "ch5",        "name": "第5章（最終以外）", "link": "承前半終（43〜49%）", "position": "43〜49%", "volume": "全体の10%"},
    {"order": 13, "key": "ch1_final",  "name": "第1章最終",  "link": "非日常突入（15%）",  "position": "15%",      "volume": "全体の1%"},
    {"order": 14, "key": "ch1",        "name": "第1章（最終以外）", "link": "起（3〜14%）", "position": "3〜14%", "volume": "全体の10〜15%"},
    {"order": 15, "key": "prologue",   "name": "プロローグ", "link": "プロローグ（0〜2%）", "position": "0〜2%",   "volume": "全体の1〜2%"},
]


def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}
    paths = {
        "s14": base / "s14_plot_main"    / f"s14_plot_latest_{novel_type}.md",
        "s18": base / "s18_foreshadow"   / f"s18_foreshadow_latest_{novel_type}.md",
        "s19": base / "s19_act_structure" / f"s19_act_latest_{novel_type}.md",
    }
    limits = {"s14": 1500, "s18": 1500, "s19": 1500}
    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""
    return results


def build_chapter_prompt(ch: dict, ctx: dict) -> str:
    return f"""以下の情報を基に、「{ch['name']}」のシーン構成を設計してください。

【{ch['name']}の定義】
・四幕との紐づけ：{ch['link']}
・位置：{ch['position']}
・ボリューム：{ch['volume']}

【全体プロット（S14）】
{ctx.get('s14', '')[:1000]}

【起承転結設計（S19）】
{ctx.get('s19', '')[:1000]}

【伏線設計（S18）】
{ctx.get('s18', '')[:800]}

以下の形式で出力してください：

---

### {ch['name']}のシーン構成

**この章の役割：**
**主人公の欠落への作用：**

#### シーン1
**内容：**（何が起きるか）
**欠落への作用：**
**配置/回収する伏線ID：**
**章末・シーン末フック：**
**文字数目安：**

#### シーン2
（同形式）

#### シーン3（任意）
（同形式）

**この章全体のフック（次章への引き）：**
"""


def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    novel_type = config.get("novel_type", "long")

    # long専用チェック
    if novel_type != "long":
        print(f"\n[S20] 章プロット設計はlong専用です。")
        print(f"  {novel_type}の場合はS19→S21へ直接進んでください。")
        print(f"  コマンド例: python run_pipeline.py --skill 21 --type {novel_type}")
        return {"skipped": True}

    token    = config["api_keys"]["notion_token"]
    plot_db  = config["notion_dbs"].get("plot_db", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S20] 章プロット設計スキル 開始（long専用）")
    print(f"  設計章数: {len(LONG_CHAPTERS)}章（プロローグ・エピローグ含む・どんでん返し逆算順）")

    ctx = load_prev_outputs(novel_type)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for ch in LONG_CHAPTERS:
        print(f"  [{ch['order']}/{len(LONG_CHAPTERS)}] {ch['name']} 設計中...")
        result = call_claude_sonnet(build_chapter_prompt(ch, ctx))
        all_results[ch["key"]] = result

        filepath = OUTPUT_DIR / f"s20_long_{ch['order']:02d}_{ch['key']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 章プロット：{ch['name']}\n実行日時：{timestamp}\n\n---\n\n{result}")
        print(f"  [OK] Saved: {filepath.name}")

    # 統合サマリー
    order = ["prologue","ch1","ch1_final","ch2","ch3","ch4","ch5","ch5_final",
             "ch6","ch7","ch8","ch8_final","ch9","ch10","epilogue"]
    ch_names = {c["key"]: c["name"] for c in LONG_CHAPTERS}
    summary = f"# 章プロット統合サマリー\n実行日時：{timestamp}\n\n---\n\n"
    for key in order:
        summary += f"## {ch_names.get(key, key)}\n{all_results.get(key,'')[:300]}\n\n---\n\n"
    summary_path = OUTPUT_DIR / f"s20_long_summary_{timestamp}.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    latest_path = OUTPUT_DIR / f"s20_chapter_latest_long.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"  [OK] Summary: {summary_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_章プロット設計")},
            "スキル":     {"rich_text": txt("S20_章プロット設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "章プロット統合サマリー", summary)

    print("[S20] 完了\n")
    print("  次のステップ: S21（余白設計）")
    print("  コマンド例: python run_pipeline.py --skill 21 --type long")
    return {"result": all_results, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="long",
                        choices=["short", "medium", "long"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"] = args.type
    run(config=_config)
