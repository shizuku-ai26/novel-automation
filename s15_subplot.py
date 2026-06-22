# -*- coding: utf-8 -*-
"""
S15：並行線（サブプロット）設計スキル
呼び出し：python run_pipeline.py --skill 15 --type short
役割：サブプロットを「テーマを立体化する装置」として設計する。
     並行線14パターンから最適なものを選択し、
     メインプロットとの関係を設計する。

重要思想：
  弱いサブプロット：「恋愛サブストーリー」「友情エピソード」
  強いサブプロット：「主線のテーマを別の角度から照射する」
                   「主線が答えを出せない問いにサブが先に答える」

次ステップ：S16（主線と並行線の距離感設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s15_subplot"


# ============================================================
# 並行線14パターン定義
# ============================================================

PARALLEL_PATTERNS = {
    "P01": {
        "name": "大弧型",
        "type": "拡散型",
        "desc": "起→転に大きな弧。序盤から転で初合流。",
        "structure": "物語序盤から独立して動き、転（75%）で初めてメインプロットと交差する。",
        "drama": "転の衝撃をサブが「予言していた」構造。どんでん返しの強度を増幅する。",
    },
    "P02": {
        "name": "二段弧型",
        "type": "拡散型",
        "desc": "起→ミッドポイント＋ミッドポイント→転の2段弧。",
        "structure": "中盤と転で2回合流。主線に2回影響を与える。",
        "drama": "ミッドポイントの目的変化と転のどんでん返しの両方に関与する。",
    },
    "P03": {
        "name": "早期収束型",
        "type": "拡散型",
        "desc": "序盤の弧の後、ミッドポイントから並走。",
        "structure": "中盤以降は主線と並走し、常に影響を与え続ける。",
        "drama": "相方キャラの並行線として機能しやすい。",
    },
    "P04": {
        "name": "後半合流型",
        "type": "収束型",
        "desc": "並走→ミッドポイント→転で大きく接近。",
        "structure": "後半で大きく接近し転で合流。",
        "drama": "「実はずっとそこにいた」という気づきを生む。",
    },
    "P05": {
        "name": "後半小弧型",
        "type": "収束型",
        "desc": "並走→ミッドポイント→転で小さく接近。",
        "structure": "後半で小さく接近。主線への影響は限定的だが確実。",
        "drama": "「そっと支えていた」構造。",
    },
    "P06": {
        "name": "前半小弧型",
        "type": "収束型",
        "desc": "並走→承前半のみ接近、後は遠ざかる。",
        "structure": "前半のみ主線に接近。後半は独自に動く。",
        "drama": "序盤の「助け」が後半に別の形で回収される。",
    },
    "P07": {
        "name": "A出発大弧型",
        "type": "A出発型",
        "desc": "承前半から転まで大きく弧を描く。",
        "structure": "物語中盤から登場し、転まで存在感を増し続ける。",
        "drama": "「遅れてきた重要人物」が転を決定的に変える。",
    },
    "P08": {
        "name": "A出発二段弧型",
        "type": "A出発型",
        "desc": "承前半から登場し、ミッドポイントと転の2点で合流。",
        "structure": "中盤以降に登場し2回主線に影響を与える。",
        "drama": "登場が遅い分、インパクトが大きい。",
    },
    "P09": {
        "name": "外部参入A型",
        "type": "外部参入型",
        "desc": "物語外から降下→承前半で合流。途中から乱入。",
        "structure": "物語外部から突然参入し、主線を変質させる。",
        "drama": "「予期しない変数」として主線を揺さぶる。",
    },
    "P10": {
        "name": "外部参入A二段型",
        "type": "外部参入型",
        "desc": "外部→承前半合流→ミッドポイント→転の二段弧。",
        "structure": "外部参入後に2回主線と交差する。",
        "drama": "対立者の並行線として機能しやすい。",
    },
    "P11": {
        "name": "外部参入A大弧型",
        "type": "外部参入型",
        "desc": "外部→承前半合流→転まで大弧。",
        "structure": "参入後に大きく弧を描き転で最大の衝撃を与える。",
        "drama": "どんでん返しの「主役」になる並行線。",
    },
    "P12": {
        "name": "完全並走型",
        "type": "並走型",
        "desc": "終始並走。合流なし。",
        "structure": "メインプロットと交差しない独立したサブプロット。",
        "drama": "テーマの対比装置。「もし主人公が別の選択をしたら」を体現する。",
    },
    "P13": {
        "name": "緩降下C型",
        "type": "降下型",
        "desc": "高位置から緩やかに降下→転で合流。",
        "structure": "ずっと高い視点から主線を「見下ろし」、転で交差する。",
        "drama": "「ずっと知っていた者」が転で真実を明かす構造。",
    },
    "P14": {
        "name": "緩降下B型",
        "type": "降下型",
        "desc": "高位置から緩やかに降下→ミッドポイントで合流。",
        "structure": "ミッドポイントで主線に影響を与え、その後は収束する。",
        "drama": "主人公の目的変化を「引き起こす」存在。",
    },
}

PATTERN_KEYS = list(PARALLEL_PATTERNS.keys())


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s7":  base / "s07_philosophy" / f"s07_philosophy_latest_{novel_type}.md",
        "s9":  base / "s09_theme"      / f"s09_theme_latest_{novel_type}.md",
        "s10": base / "s10_character"  / f"s10_character_latest_{novel_type}.md",
        "s14": base / "s14_plot_main"  / f"s14_plot_latest_{novel_type}.md",
    }
    limits = {"s7": 1500, "s9": 1500, "s10": 1500, "s14": 1500}

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

    # パターンテーブル
    pattern_table = "\n".join(
        f"・{k}（{v['name']}）[{v['type']}]：{v['desc']} → ドラマ：{v['drama']}"
        for k, v in PARALLEL_PATTERNS.items()
    )

    return f"""あなたはこの小説作品の「並行線設計者」です。
サブプロットを「テーマを立体化する装置」として設計してください。

重要思想：
・サブプロットはメインプロットの「テーマの別の角度」を体現する
・メインプロットが答えられない問いに、サブが別の答えを示す
・サブプロットは「装飾」ではなく「テーマの第二の旅」

【並行線14パターン】
{pattern_table}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S14 全体プロット設計（引き渡しパラメータ含む）】
{prev.get("s14_table") or prev["s14"]}

【S10 キャラクター設計（サブキャラの情報）】
{prev["s10"]}

【S9 テーマ設計（大テーマ・体現者）】
{prev["s9"]}

【S7 哲学的問い（サブの問いとの接続）】
{prev["s7"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 並行線設計書（S15）

---

## ■ 並行線の選定

**並行線①（相方キャラ）：**
・パターン：（P01〜P14から選択）
・選定理由：

**並行線②（サブキャラ）：**
・パターン：（P01〜P14から選択）
・選定理由：

**並行線③（対立者）：**
・パターン：（P01〜P14から選択）
・選定理由：

---

## ■ 並行線①（相方キャラ）の詳細設計

**このサブプロットが体現するテーマの側面：**
（メインプロットとは異なる角度からどのテーマを照射するか）

**サブプロットの問い：**
（メインの核心の問いとは異なる、相方固有の問い）

**起：**（相方キャラの物語開始時の状況・目的）
**承前半：**（主線との最初の接近・影響）
**ミッドポイント：**（相方の目的の変化）
**承後半：**（主線への収束 / 離散の動き）
**転：**（主線のどんでん返しとどう交差するか）
**結以降：**（どんでん返し後の役割）

**このサブプロットがなければ描けないもの：**

---

## ■ 並行線②（サブキャラ）の詳細設計

**このサブプロットが体現するテーマの側面：**
**サブプロットの問い：**
**起：** / **承：** / **転：** / **結：**
**主線との交差タイミングと影響：**
**このサブプロットがなければ描けないもの：**

---

## ■ 並行線③（対立者）の詳細設計

**このサブプロットが体現するテーマの側面：**
（対立者はテーマの「正反対の答え」を体現する並行線）
**起：** / **承：** / **転：** / **結：**
**どんでん返しとの直接的な接続：**
（S1のどんでん返し構造において対立者の並行線がどう機能するか）

---

## ■ 並行線の絡み合い設計

複数の並行線が主線・互いにどう絡み合うかを整理：

| 交差点 | 位置（%） | 関与する並行線 | 主線への影響 |
|------|:--------:|------------|----------|
| | | | |
| | | | |
| | | | |

**最も大きなドラマが生まれる絡み合いポイント（3つ）：**
  ①
  ②
  ③

---

## ■ S16（距離感設計）への引き渡しパラメータ

| 並行線 | 独立度（1〜5） | 交差頻度（1〜5） | テーマ共鳴度（1〜5） |
|------|:----------:|:-----------:|:------------:|
| 相方キャラ | | | |
| サブキャラ | | | |
| 対立者 | | | |

**各並行線の「最適な距離感」の仮説：**
（S16で詳細設計するための方向性）
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

    print("\n[S15] 並行線設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  並行線パターン: {len(PARALLEL_PATTERNS)}パターン")

    prev = load_prev_outputs(novel_type)

    # fix②: S14のS15引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s14_path = _Path(__file__).parent.parent / "output" / "s14_plot_main" \
               / f"s14_plot_latest_{novel_type}.md"
    if _s14_path.exists():
        _s14_full = _s14_path.read_text(encoding="utf-8")
        _idx = _s14_full.rfind("## ■ S15（並行線設計）への引き渡しパラメータ")
        prev["s14_table"] = _s14_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s14_table"] = ""

    prompt = build_prompt(prev, novel_type)
    print("  並行線設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 並行線設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s15_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s15_subplot_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_並行線設計")},
            "スキル":     {"rich_text": txt("S15_並行線設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "並行線設計", result)

    print("[S15] 完了\n")
    print("  次のステップ: S16（主線と並行線の距離感設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 16 --type {novel_type}")

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
