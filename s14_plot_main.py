# -*- coding: utf-8 -*-
"""
S14：全体プロット設計スキル
呼び出し：python run_pipeline.py --skill 14 --type short
役割：S1〜S13の全設計を統合し、物語全体のプロット構造を設計する。
     「イベント列」ではなく「主人公が問いに対峙する過程」として設計。
     S1のどんでん返しから逆算して起承転結を構築する。

重要思想：
  弱いプロット：「事件A→解決→事件B→解決→...」
  強いプロット：「欠落を持つ主人公が問いに追い詰められ、
               どんでん返しで問いの意味が書き換わり、
               欠落と向き合う選択をする」

次ステップ：S15（並行線設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s14_plot_main"


# ============================================================
# 四幕構成定義
# ============================================================

FOUR_ACT_STRUCTURE = """
【四幕構成（どんでん返し逆算型）】

■ 転（75%）：どんでん返し発生
  → 最初に設計する。全てはここから逆算する。
  → 「事実の反転」ではなく「価値観の反転」
  → 主人公の「問いへの答え」が全て書き換わる瞬間

■ 結（75〜98%）：クライマックス〜解決
  → どんでん返し後のどん底から再起
  → 欠落と向き合う最後の選択
  → 読後感が生まれる場所

■ 承（16〜74%）：展開・深化
  ├── 承前半（16〜49%）：問いが深まる・欠落が機能し始める
  ├── ミッドポイント（50%）：主人公の目的が変化する
  └── 承後半（50〜74%）：問いの答えが崩れ始める・転の準備

■ 起（3〜15%）：日常と欠落の提示
  → 主人公の欠落が「見える」（読者には）
  → 問いの種を日常に埋め込む
  → 非日常突入（15%）：世界が変わる

■ プロローグ（0〜2%）：最初の問い
  → 冒頭1文で「認識反転の予告」
  → 読者を掴む「違和感・事件・感情」のどれかで始まる
"""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s1":  base / "s01_plot_twist"    / f"s01_twist_latest_{novel_type}.md",
        "s2":  base / "s02_submission"    / f"s02_submission_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"    / f"s07_philosophy_latest_{novel_type}.md",
        "s8":  base / "s08_emotion"       / f"s08_emotion_latest_{novel_type}.md",
        "s9":  base / "s09_theme"         / f"s09_theme_latest_{novel_type}.md",
        "s13": base / "s13_deficiency"    / f"s13_deficiency_latest_{novel_type}.md",
    }
    limits = {
        "s1": 1500, "s2": 1000, "s7": 1500,
        "s8": 1500, "s9": 1500, "s13": 1500,
    }

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

def build_prompt(prev: dict, contest_key: str, novel_type: str,
                 world_setting: str = "", setting_confirmed: dict = None) -> str:

    contest_note = ""
    # 世界観・確定設定セクション
    world_lines = []
    if world_setting:
        world_lines.append(f"・世界観：{world_setting}")
    if setting_confirmed:
        if setting_confirmed.get("organization_type"):
            world_lines.append(f"・組織A（対立者）の外形：{setting_confirmed['organization_type']}")
        if setting_confirmed.get("organization_irony"):
            world_lines.append(f"・{setting_confirmed['organization_irony']}")
        if setting_confirmed.get("monster_return_place"):
            world_lines.append(f"・怪物の帰る場所：{setting_confirmed['monster_return_place']}")
        if setting_confirmed.get("monster_return_sign"):
            world_lines.append(f"・怪物の帰還サイン：{setting_confirmed['monster_return_sign']}")
    world_section = (
        "【確定済み世界観・設定（プロット設計に必ず反映）】\n"
        + "\n".join(world_lines) + "\n"
    ) if world_lines else ""

    if contest_key == "note":
        contest_note = "※note（short=〜5万字）：プロットは「感情の変化」を軸に。冒頭3行・感情フック必須。全体15〜25話・各話2000〜2500字を目安に設計（最大5万字まで使ってよい）。S2の「6章構成」はあくまで叩き台なので、実際の話数はS1〜S13の設計から最適値を判断すること。"
    elif contest_key == "kakugawa_chara":
        contest_note = "※角川：続刊を想定した構造。各章末に次を読みたくなる疑問を仕込む。"
    elif contest_key == "kakuyomu":
        contest_note = "※カクヨム：第一話に全力。毎話フックを設計。テンポ最優先。"
    elif contest_key == "everystory":
        contest_note = "※エブリスタ：コマ映えする山場を均等配置。感情爆発シーンを3か所以上。"

    return f"""あなたはこの小説作品の「プロット設計者」です。
S1〜S13の全設計を統合し、どんでん返しから逆算して
物語全体のプロット構造を設計してください。

{world_section}
{FOUR_ACT_STRUCTURE}

重要思想：
・プロットは「主人公が問いに対峙する過程」として設計する
・イベント列（事件A→B→C）ではなく「欠落の旅」として設計する
・各場面は「この場面が欠落にどう作用するか」を持つ
・全ての出来事が「どんでん返し後に意味が変わる」よう設計する

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S1 どんでん返し設計（転の核）】
{prev["s1"]}

【S7 哲学的問い（プロットのOS）】
{prev["s7"]}

【S9 テーマ設計（大テーマ・揺らぎ）】
{prev["s9"]}

【S13 欠落分析（S14引き渡しパラメータ）】
{prev.get("s13_table") or prev["s13"]}

【S8 感情設計（感情波形・読後感）】
{prev["s8"]}

【S2 投稿形態（コンテスト制約）】
{prev["s2"]}

{contest_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 全体プロット設計書（S14）

---

以下の形式で出力してください。
設計順序はどんでん返しから完全逆算です。この順番で設計することで伏線の必然性が高まります。

---

## ■ プロットの核心（1文）

**この物語が描くこと：**
（「〜な主人公が〜という問いに追い詰められ〜という選択をする」という形で）

---

## ■ ① 転（75%）：どんでん返しの設計【最初に確定】

**どんでん返しの瞬間：**
（何が・誰によって・どのように明かされるか）

**どんでん返しによる意味の反転の内容：**
（読者がそれまで信じていたことが、実はどういうことだったか）

**主人公の「問いへの答え」がどう書き換わるか：**
（転前の答え → 転後の答え）

**欠落がこの瞬間どう機能するか：**

---

## ■ ② 結（75〜98%）【転の直後を確定】

**どんでん返し直後のどん底：**
（価値観が崩れた主人公の状態）

**再起のきっかけ：**
（何が・誰が主人公を動かすか）

**クライマックス：**
（欠落と向き合う最後の選択場面）

**解決の形：**
（完全解決 / 部分解決 / 未解決のどれか・理由）

---

## ■ ③ ミッドポイント（50%）【転の起点を確定】

**主人公の目的が変化する瞬間：**
（何をきっかけに・どう変化するか）

**ミッドポイント前後での主人公の「問いへの答え」の変化：**

**S8感情波形のミッドポイントでの状態：**

---

## ■ ④ 承後半（50〜74%）【転への道筋を確定】

**この章で崩れ始めるもの：**
**転の準備として積み上げるもの：**
**読者が「何かが違う」と感じ始める描写：**
**どんでん返し直前の「最高の緊張」の設計：**

---

## ■ ⑤ 承前半（16〜49%）【伏線を逆算配置】

**この章で深まる問い：**
**欠落が初めて「痛み」になる場面：**
**承前半に配置する伏線（転で回収されるもの）：**
  伏線①：
  伏線②：
  伏線③：
**サブプロットの展開（S15で詳細設計）：**

---

## ■ ⑥ 起（3〜15%）【欠落と問いの種を逆算配置】

**この章で描くこと：**
**提示する欠落（読者には見えるが主人公は気づいていない）：**
**埋め込む問いの種：**
**非日常突入（15%）のきっかけ：**

---

## ■ ⑦ プロローグ（0〜2%）【最後に冒頭を設計】

**冒頭1文（確定案）：**
（感情型 / 事件型 / 違和感型 のどれかで）

**プロローグで提示するもの：**
**プロローグに仕込む「認識反転の予告」：**
（転後に振り返ると意味が変わる描写）

---

## ■ ⑧ エピローグ（98〜100%）

**読後感を生み出す最後の場面：**
**「認識反転の余韻」の設計：**
（転後の真実を踏まえてプロローグを振り返ると何が見えるか）
**最後の1文：**

---

## ■ プロット全体の整合性チェック

**全ての出来事が「転後に意味が変わる」確認：**
（各幕の主要場面が転後にどう見え方が変わるかを列挙）
| 幕 | 場面 | 転前の意味 | 転後の意味 |
|---|-----|---------|---------|
| 起 | | | |
| 承前半 | | | |
| ミッド | | | |
| 承後半 | | | |
| 転 | | | |
| 結 | | | |

**欠落が「都合よく解決されない」確認：**
（S13で定めた欠落制約が守られているか）

---

## ■ S15（並行線設計）への引き渡しパラメータ

**メインプロットの骨格（1〜2文）：**
**並行線が必要な理由：**
（メインプロットだけでは描けないテーマの側面）
**サブキャラの並行線候補：**
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token       = config["api_keys"]["notion_token"]
    plot_db     = config["notion_dbs"].get("plot_db", "")
    novel_type  = config.get("novel_type", "short")
    contest_key = config.get("contest", None)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S14] 全体プロット設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    # fix③: S13のS14引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s13_path = _Path(__file__).parent.parent / "output" / "s13_deficiency" \
               / f"s13_deficiency_latest_{novel_type}.md"
    if _s13_path.exists():
        _s13_full = _s13_path.read_text(encoding="utf-8")
        _idx = _s13_full.rfind("## ■ S14（全体プロット設計）への引き渡しパラメータ")
        prev["s13_table"] = _s13_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s13_table"] = ""

    world_setting    = config.get("world_setting", "")
    setting_confirmed = config.get("setting_confirmed", {})
    if world_setting:
        print(f"  世界観制約: {world_setting}")
    if setting_confirmed:
        print(f"  確定済み設定: {len(setting_confirmed)}件を注入")
    prompt = build_prompt(prev, contest_key, novel_type, world_setting, setting_confirmed)
    print("  プロット設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 全体プロット設計
実行日時：{timestamp}
小説タイプ：{novel_type}
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s14_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s14_plot_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_全体プロット設計")},
            "スキル":     {"rich_text": txt("S14_全体プロット設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "全体プロット設計", result)

    print("[S14] 完了\n")
    print("  次のステップ: S15（並行線設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 15 --type {novel_type}")

    return {"result": result, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"] = args.type
    _config["contest"]    = args.contest
    run(config=_config)
