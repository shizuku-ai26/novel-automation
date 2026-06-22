# -*- coding: utf-8 -*-
"""
S21：余白設計スキル
呼び出し：python run_pipeline.py --skill 21 --type short
役割：AI臭除去の核。意図的に「説明しない・回収しない・真偽不明・
     解釈余地」を残す設計を行う。
     全てを説明するとAI生成の「平均的な小説」になる。

重要思想：
  余白とは「書かないことの設計」
  ・説明しない：読者の想像に委ねる
  ・回収しない：答えを出さない伏線
  ・真偽不明：どちらとも取れる描写
  ・解釈余地：読者によって意味が変わる場面

次ステップ：S22（シーン別感情設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s21_margin"


# ============================================================
# 余白の4種類定義
# ============================================================

MARGIN_TYPES = {
    "unsaid": {
        "label":   "語らない余白",
        "desc":    "説明すれば伝わるが、あえて書かない",
        "example": "主人公が泣いた理由を書かない。読者が感じ取る",
        "effect":  "読者が「自分で気づいた」感覚を持つ。感情移入が深まる",
        "risk":    "書きすぎると意味が伝わらない。程度が重要",
    },
    "unclosed": {
        "label":   "回収しない余白",
        "desc":    "提示したが答えを出さない伏線・謎",
        "example": "主人公が幼少期に言いかけた言葉が最後まで明かされない",
        "effect":  "読後に読者が考え続ける。再読欲が生まれる",
        "risk":    "重要な伏線を回収しないと「作者の忘れ物」に見える",
    },
    "ambiguous": {
        "label":   "真偽不明の余白",
        "desc":    "どちらとも取れる描写。読者が解釈を選ぶ",
        "example": "相方の最後の笑顔が「赦し」なのか「諦め」なのか書かない",
        "effect":  "読者によって意味が変わる。議論・感想が生まれる",
        "risk":    "意図的な曖昧さと「ただ不明瞭な描写」は違う",
    },
    "interpretable": {
        "label":   "解釈余地の余白",
        "desc":    "場面の意味を複数の読み方が可能な設計",
        "example": "同じ台詞が「愛の告白」にも「別れの言葉」にも読める",
        "effect":  "初読と再読で意味が変わる。どんでん返し後の再読価値が高まる",
        "risk":    "狙いすぎると「わかりにくい小説」になる",
    },
}

# 文学性×余白の対応（S2の6軸で調整）
LITERARY_MARGIN_GUIDE = {
    (0,  29):  "文学性が低い設定。余白は最小限に。読者を置いてけぼりにしない。",
    (30, 49):  "文学性が中程度。語らない余白を中心に2〜3か所。",
    (50, 69):  "文学性が高め。4種の余白をバランスよく使う。",
    (70, 100): "文学性が高い設定。余白を積極的に使う。ただし回収しない余白は1〜2か所まで。",
}

def get_literary_guide(literary_score: int) -> str:
    for (lo, hi), guide in LITERARY_MARGIN_GUIDE.items():
        if lo <= literary_score <= hi:
            return guide
    return ""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s2":  base / "s02_submission"   / f"s02_submission_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"   / f"s07_philosophy_latest_{novel_type}.md",
        "s14": base / "s14_plot_main"    / f"s14_plot_latest_{novel_type}.md",
        "s19": base / "s19_act_structure" / f"s19_act_latest_{novel_type}.md",
    }
    limits = {"s2": 1500, "s7": 1500, "s14": 1500, "s19": 1500}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""

    # S2 JSONから文学性スコアを取得
    s2j = base / "s02_submission" / f"s02_params_latest_{novel_type}.json"
    results["literary_score"] = 50  # デフォルト
    if s2j.exists():
        import json
        with open(s2j, encoding="utf-8") as f:
            params = json.load(f)
        results["literary_score"] = params.get("weights", {}).get("literary", 50)
        print(f"  [INFO] 文学性スコア: {results['literary_score']}/100")

    return results


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(prev: dict, novel_type: str) -> str:

    literary_score = prev.get("literary_score", 50)
    literary_guide = get_literary_guide(literary_score)

    types_text = "\n".join(
        f"【{v['label']}（{k}）】\n"
        f"  概要：{v['desc']}\n"
        f"  例：{v['example']}\n"
        f"  効果：{v['effect']}\n"
        f"  リスク：{v['risk']}"
        for k, v in MARGIN_TYPES.items()
    )

    return f"""あなたはこの小説作品の「余白設計者」です。
意図的に「説明しない・回収しない・真偽不明・解釈余地」を設計してください。

重要思想：
・余白は「書けなかった部分」ではなく「書かない設計」
・AI生成の最大の弱点は「全て説明してしまうこと」
・余白があることで読者は「自分で発見した」感覚を持つ
・余白は読後感を深め、再読価値を高める

【S2文学性スコア：{literary_score}/100】
{literary_guide}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【余白の4種類】
{types_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S7哲学的問い（余白の核となる問い）】
{prev["s7"]}

【S14全体プロット（何を説明しないかの基準）】
{prev["s14"]}

【S19起承転結設計（各章の場面・S22引き渡しパラメータ含む）】
{prev.get("s19_table") or prev["s19"]}

【S2投稿形態（コンテスト制約）】
{prev["s2"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 余白設計書（S21）

---

## ■ 余白設計の方針

**この作品の「余白レベル」：**（文学性{literary_score}から導いた方針）
**最も大切にする余白の種類：**（4種のうち優先順）
**余白を使わない場所：**（明示的に説明すべき場所）

---

## ■ 語らない余白（unsaid）

### U-1
**場面・位置（%）：**
**書かない内容：**（何を説明しないか）
**なぜ書かないか：**（読者に何を感じ取らせるか）
**代わりに書くもの：**（身体描写・沈黙・行動で代替する方法）

### U-2
**場面・位置・書かない内容・代替表現：**

### U-3（任意）

---

## ■ 回収しない余白（unclosed）

### UC-1
**提示する謎・伏線：**
**なぜ回収しないか：**（この謎が未解決のまま残ることの価値）
**読後に読者が考え続けること：**
**「作者の忘れ物」に見えないための工夫：**

### UC-2（任意）
（文学性50以下の場合は1か所まで推奨）

---

## ■ 真偽不明の余白（ambiguous）

### A-1
**場面・位置（%）：**
**どちらとも読める描写：**
**解釈① ：**（こう読める）
**解釈② ：**（こうも読める）
**どちらの解釈が「当たり」か著者は明かさない理由：**
**再読時に意味が変わる仕掛け：**

---

## ■ 解釈余地の余白（interpretable）

### I-1
**場面・位置（%）：**
**複数の意味を持つ台詞・描写：**
**読み方①（初読）：**
**読み方②（転後の再読）：**
**この余白がどんでん返しの余韻を深める方法：**

---

## ■ 余白マップ（全体）

| ID | 種別 | 位置（%） | 内容（1文） | 効果 |
|----|------|:--------:|---------|-----|
| U-1 | 語らない | | | |
| U-2 | 語らない | | | |
| UC-1 | 回収しない | | | |
| A-1 | 真偽不明 | | | |
| I-1 | 解釈余地 | | | |

---

## ■ AI臭除去チェックリスト

以下の「AI生成あるある」が混入していないか確認してください：

**説明過多の危険ゾーン（この作品で特に注意すべき場所）：**
（どのシーンで感情を直接書いてしまいがちか）

**「ため」「ので」の多用：**（因果関係の説明過多）
（削除または行動で示すべき箇所）

**内的独白の多用：**（主人公が自分の感情を分析する）
（代替できる身体描写・行動・沈黙の例）

---

## ■ S22（シーン別感情設計）への引き渡しパラメータ

**余白が機能する感情状態のリスト：**
（どの感情の瞬間に余白が最も深く機能するか）

**「余白のある感情描写」の具体例（3つ）：**
（感情を書かずに感情を伝える具体的な描写例）
  例①：
  例②：
  例③：
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

    print("\n[S21] 余白設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    # fix①: S19のS22引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s19_path = _Path(__file__).parent.parent / "output" / "s19_act_structure" \
               / f"s19_act_latest_{novel_type}.md"
    if _s19_path.exists():
        _s19_full = _s19_path.read_text(encoding="utf-8")
        _idx = _s19_full.rfind("## ■ S20（章プロット設計）への引き渡しパラメータ")
        if _idx < 0:
            _idx = _s19_full.rfind("## ■ S21")
        prev["s19_table"] = _s19_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s19_table"] = ""

    prompt = build_prompt(prev, novel_type)
    print("  余白設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 余白設計
実行日時：{timestamp}
小説タイプ：{novel_type}
文学性スコア：{prev.get('literary_score', 50)}/100

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s21_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s21_margin_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_余白設計")},
            "スキル":     {"rich_text": txt("S21_余白設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "余白設計", result)

    print("[S21] 完了\n")
    print("  次のステップ: S22（シーン別感情設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 22 --type {novel_type}")

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
