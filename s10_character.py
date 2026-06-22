# -*- coding: utf-8 -*-
"""
S10：キャラクター設計スキル
呼び出し：python run_pipeline.py --skill 10 --type short
役割：S3〜S9の全出力を統合し、登場人物を「問いの体現者」として設計する。
     キャラはテーマ装置ではなく「哲学的問いを生きる存在」として設計する。

設計対象：主人公・相方・対立者（敵または偽敵）・サブキャラ
次ステップ：S11（X軸Y軸性格設計）

config.yaml 対応パラメータ:
  novel_type: "short" / "medium" / "long"
  char_count: 登場人物数（省略時: 4）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s10_character"


# ============================================================
# 重要思想
# ============================================================

CHARACTER_PHILOSOPHY = """
【キャラクター設計の核心思想】

❌ テーマ装置としてのキャラクター（避けるべき）
  → 「愛の大切さを教える役割」
  → 「正義を体現するキャラ」
  → メッセージのスピーカーになっている

✅ 問いの体現者としてのキャラクター
  → 「この問いを生きている存在」
  → 問いに対して「異なる答え」を行動で示す
  → 問いが答えられないまま終わる者もいる

【問いの体現者の設計ルール】
1. 主人公は「問いに最も傷ついている人物」として設計する
2. 相方は「主人公が気づいていない問いの別側面」を見せる
3. 対立者は「問いに対して正反対の答えを体現する」
4. サブキャラは「問いの第三の視点・世界の広さ」を示す
5. 誰も問いに「正解を語らない」
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
        "s3":  base / "s03_age_design"    / f"s03_age_latest_{novel_type}.md",
        "s4":  base / "s04_age_gap"       / f"s04_age_gap_latest_{novel_type}.md",
        "s5":  base / "s05_gender_design" / f"s05_gender_latest_{novel_type}.md",
        "s6":  base / "s06_gravity"       / f"s06_gravity_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"    / f"s07_philosophy_latest_{novel_type}.md",
        "s8":  base / "s08_emotion"       / f"s08_emotion_latest_{novel_type}.md",
        "s9":  base / "s09_theme"         / f"s09_theme_latest_{novel_type}.md",
    }
    limits = {
        "s1": 1500, "s2": 1000, "s3": 1500, "s4": 1500,
        "s5": 1500, "s6": 1500, "s7": 1500, "s8": 1500, "s9": 1500,
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

def build_prompt(prev: dict, char_count: int,
                 contest_key: str, novel_type: str,
                 extra_char_role: str = "",
                 forbidden_names: list = None,
                 setting_confirmed: dict = None) -> str:

    # 使用禁止名の注入
    forbidden_text = ""
    if forbidden_names:
        forbidden_text = (
            "\n【使用禁止の名前】以下は過去作品で使用済みのため絶対に使わないこと：\n"
            + ", ".join(forbidden_names) + "\n"
        )

    # 確定済み設定メモの注入
    setting_text = ""
    if setting_confirmed:
        lines = ["\n【確定済み設定（必ず遵守）】"]
        if setting_confirmed.get("organization_type"):
            lines.append(f"・組織A（対立者）の外形：{setting_confirmed['organization_type']}")
        if setting_confirmed.get("organization_irony"):
            lines.append(f"・{setting_confirmed['organization_irony']}")
        if setting_confirmed.get("monster_return_place"):
            lines.append(f"・怪物の帰る場所：{setting_confirmed['monster_return_place']}")
        if setting_confirmed.get("monster_return_sign"):
            lines.append(f"・怪物の帰還サイン：{setting_confirmed['monster_return_sign']}")
        setting_text = "\n".join(lines) + "\n"

    # 5人目の追加キャラ設計ヒント
    extra_role_label = extra_char_role or "サブキャラ②（追加）"
    if char_count >= 5:
        extra_roles_desc  = f"（主人公 / 相方 / 対立者 / サブキャラ① / {extra_role_label}）"
        extra_table_row   = f"| {extra_role_label} | | | | | |\n"
        extra_char_hint   = (
            f"\n【5人目の追加キャラ指示】\n"
            f"役割：{extra_role_label}\n"
            f"主人公・相方・対立者・サブキャラ①とは異なる視点を物語に加える。\n"
            f"この人物の設計も他キャラと同じ詳細度で行うこと（S11メモまで含む）。\n"
        )
        extra_char_section = "\n---\n\n## ■ サブキャラ②の設計\n\n**名前（仮）：**\n**年齢：**\n**性別：**\n\n**問いとの関係：**\n（このキャラが問いにどう関わるか）\n\n**S9テーマの「欠落」との接続：**\n\n**外見の第一印象：**\n\n**口癖・動作の癖：**\n\n**S11（性格設計）へのメモ：矛盾の核：**"
    else:
        extra_roles_desc  = "（主人公 / 相方 / 対立者 / サブキャラ）"
        extra_table_row   = ""
        extra_char_hint   = ""
        extra_char_section = ""
    subchar_label = "サブキャラ①" if char_count >= 5 else "サブキャラ"

    contest_note = ""
    if contest_key == "note":
        contest_note = "※note：キャラは「感情で読まれる」。内面の痛みを身体描写で示す設計を優先。"
    elif contest_key == "kakugawa_chara":
        contest_note = "※角川：主人公は「推したくなる」存在に。欠点があっても愛せる魅力が必須。"
    elif contest_key == "kakuyomu":
        contest_note = "※カクヨム：主人公は第一話で「強さ・快感・個性」を印象づける。"
    elif contest_key == "everystory":
        contest_note = "※エブリスタ：キャラはコマ映えする。感情爆発シーンを想定した設計。"

    return f"""あなたはこの小説作品の「キャラクター設計者」です。
S3〜S9の全情報を統合し、登場人物を「問いの体現者」として設計してください。
{forbidden_text}{setting_text}
{CHARACTER_PHILOSOPHY}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S7哲学的問い（核心・補助）】
{prev["s7"]}

【S9テーマ設計（大テーマ・体現者配置）】
{prev["s9"]}

【S1どんでん返し構造】
{prev["s1"]}

【S6関係性重力（主軸・副軸）】
{prev["s6"]}

【S5性別・炸点・熱量】
{prev["s5"]}

【S4年齢差・関係タイプ】
{prev["s4"]}

【S3主人公年齢】
{prev["s3"]}

【S8読後感・感情波形】
{prev["s8"]}

{contest_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

# キャラクター設計書（S10）

---

登場人物{char_count}名分を以下の形式で設計してください：
{extra_roles_desc}
{extra_char_hint}

---

## ■ キャラクター一覧（概要）

| 役割 | 名前（仮） | 年齢 | 性別 | 問いへの立場 | 一言で言うと |
|-----|---------|:---:|:---:|-----------|----------|
| 主人公 | | | | | |
| 相方 | | | | | |
| 対立者 | | | | | |
| {subchar_label} | | | | | |
{extra_table_row}
---

## ■ 主人公の設計

**名前（仮）：**
**年齢：**（S3確定値）
**性別：**（S5確定値）

**問いとの関係：**
（核心の問いに「最も傷ついている人物」として、なぜこの人物が問いに傷つくのか）

**問いへの現在の答え（序盤）：**
（間違っていてもいい・硬直した答えを持っている）

**問いへの答えが変化する軌跡：**
・序盤：
・中盤（ミッドポイント）：
・どんでん返し後：
・結末：

**S9テーマの「欠落」との接続：**
（テーマのどの部分を体現できていない存在か）

**外見の第一印象（読者が最初に受ける印象）：**
（1〜2文・具体的に。内面を説明しない）

**口癖・動作の癖：**
（感情を直接言わないための行動・仕草）

**S11（性格設計）へのメモ：**
（矛盾として設計すべき性格の核）

---

## ■ 相方の設計

**名前（仮）：**
**年齢：**（S4確定値から算出）
**性別：**（S5確定値）

**問いとの関係：**
（主人公が気づいていない「問いの別側面」を見せる存在として）

**問いへの現在の答え（序盤）：**
（主人公と異なる答えを持っている）

**主人公の問いへの答えをどう変化させるか：**
（直接教えない・行動・存在で変化させる）

**S6重力との接続：**
（主軸重力がこのキャラとの関係でどう機能するか）

**S5炸点との接続：**
（このキャラとの炸点①②③がどう問いと絡むか）

**外見の第一印象：**

**口癖・動作の癖：**

**S11（性格設計）へのメモ：**

---

## ■ 対立者の設計

**名前（仮）：**
**年齢：**
**性別：**

**問いとの関係：**
（問いに対して「主人公と正反対の答え」を体現する存在として）

**問いへの答え（対立者が信じる答え）：**
（悪役でも「間違い」とは描かない。一つの答えとして機能する）

**S1どんでん返し構造における役割：**
（偽敵か本敵か・どんでん返しでどう機能するか）

**対立者が「間違っていない」理由：**
（読者がこの立場を理解できる根拠）

**外見の第一印象：**

**口癖・動作の癖：**

**S11（性格設計）へのメモ：**

---

## ■ サブキャラの設計

**名前（仮）：**
**年齢：**
**性別：**

**問いとの関係：**
（問いの「第三の視点」を示す・世界の広さを体現）

**物語での役割：**
（主人公・相方・対立者のどれを支え・どれと対比するか）

**S5炸点・S8感情波形との接続：**

**外見の第一印象：**

**口癖・動作の癖：**

---

## ■ キャラクター間の問いの配置図

各キャラクターが核心の問いに対してどの位置に立つかを整理：

**核心の問い：**（S7から転記）

```
主人公：（問いに最も傷ついている）
  ↕ 対立・共鳴
相方：（問いの別側面を見せる）
  ↕ 対立・否定
対立者：（問いの正反対の答えを体現）
  ↕ 補完・拡張
サブキャラ：（問いの第三の視点）
```

**どんでん返し後に配置図がどう変わるか：**
（転（75%）でキャラクターの問いへの立場がどう書き換わるか）

---

{extra_char_section}

---

## ■ S11（X軸Y軸性格設計）への引き渡しパラメータ

各キャラクターの「矛盾」の核を記載（S11で深化させる）：

| キャラ | 表の性格 | 隠れた性格 | 矛盾の核 |
|------|--------|---------|--------|
| 主人公 | | | |
| 相方 | | | |
| 対立者 | | | |
| {subchar_label} | | | |
{'| ' + extra_role_label + ' | | | |' if char_count >= 5 else ''}
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
    char_count  = int(config.get("character_count", config.get("char_count", 4)))
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S10] キャラクター設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  設計人数: {char_count}名")

    prev = load_prev_outputs(novel_type)

    forbidden = config.get("forbidden_names", [])
    if forbidden:
        print(f"  [名前チェック] 使用禁止名 {len(forbidden)}件をプロンプトに注入")
    extra_role        = config.get("extra_char_role", "")
    setting_confirmed = config.get("setting_confirmed", {})
    if setting_confirmed:
        print(f"  確定済み設定: {len(setting_confirmed)}件を注入")
    prompt = build_prompt(prev, char_count, contest_key, novel_type,
                          extra_char_role=extra_role,
                          forbidden_names=forbidden,
                          setting_confirmed=setting_confirmed)
    print("  キャラクター設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# キャラクター設計
実行日時：{timestamp}
小説タイプ：{novel_type}
設計人数：{char_count}名
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s10_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s10_character_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_キャラクター設計")},
            "スキル":     {"rich_text": txt("S10_キャラクター設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "キャラクター設計", result)

    print("[S10] 完了\n")
    print("  次のステップ: S11（X軸Y軸性格設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 11 --type {novel_type}")

    return {"result": result, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    parser.add_argument("--char-count", type=int, default=4,
                        help="設計する登場人物数（省略時: 4）")
    parser.add_argument(
                        "--extra-char-role", type=str, default="",
                        help="5人目以降の追加キャラの役割（例: 相方の友人）")
    parser.add_argument("--series", action="store_true",
                        help="連作小説モード（名前チェックをスキップ）")
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"]  = args.type
    _config["contest"]     = args.contest
    _config["character_count"] = args.char_count
    if args.extra_char_role:
        _config["extra_char_role"] = args.extra_char_role

    # 使用禁止名の読み込み（連作モード以外）
    if not args.series:
        import json
        used_path = Path(__file__).parent.parent / "output" / "used_names.json"
        if used_path.exists():
            data = json.loads(used_path.read_text(encoding="utf-8"))
            if data.get("names"):
                _config["forbidden_names"] = data["names"]

    run(config=_config)
