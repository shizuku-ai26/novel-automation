# -*- coding: utf-8 -*-
"""
S6：関係性重力設計スキル
呼び出し：python run_pipeline.py --skill 6 --type short
役割：11項目の関係性重力から主軸・副軸を選定し、
     S1価値観反転との接続・S5炸点との連動を設計する。
     S7（哲学的問い設計）へのパラメータを引き渡す。

【拡張方法】
GRAVITY_ITEMS 辞書に項目を追加するだけで自動的に対応します。
キー名は英小文字スネークケース推奨（例: "new_item"）

config.yaml 対応パラメータ:
  gravity_main:  主軸重力項目キー（省略時: AI自動選定）
  gravity_sub:   副軸重力項目キー（省略時: AI自動選定）
  novel_type: "short" / "medium" / "long"
"""

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s06_gravity"


# ============================================================
# 関係性重力 項目定義
# ────────────────────────────────────────────────────────────
# 【拡張方法】
# 新しい項目を追加する場合は GRAVITY_ITEMS に辞書を追加するだけ。
# 必須キー: label / desc / drama / dark_side / s1_fit
# s1_fit: V1〜V7 それぞれ "◎" / "○" / "△" / "×"
# ============================================================

GRAVITY_ITEMS = {
    # ── 現行11項目（v1.0） ──────────────────────────────────
    "protection": {
        "label":    "保護",
        "desc":     "一方が他方を守る。力・立場・経験の差から生まれる一方向の庇護。",
        "drama":    "守る側の「失う恐怖」・守られる側の「依存と自立の葛藤」",
        "dark_side": "保護が支配に転化するリスク。相手の自由を奪う善意。",
    },
    "dependence": {
        "label":    "依存",
        "desc":     "一方が他方なしでは機能しない状態。精神的・行動的な不可分性。",
        "drama":    "失うことへの恐怖が行動を歪める・依存を断ち切ることが成長になる",
        "dark_side": "依存が相手を縛る鎖になる。自由意志の消失。",
    },
    "worship": {
        "label":    "崇拝",
        "desc":     "一方を理想化・神格化する。現実の相手ではなく「像」を愛している状態。",
        "drama":    "像の崩壊・「普通の人間」と知ったときの衝撃と深化",
        "dark_side": "崇拝が幻滅に転化する。相手の人間性を消す暴力性。",
    },
    "complicity": {
        "label":    "共犯",
        "desc":     "秘密・罪・禁忌を共有する。「二人だけが知っている」という閉鎖的な絆。",
        "drama":    "秘密の暴露リスク・共犯が友情・愛情に転化する瞬間",
        "dark_side": "共犯関係が相手を人質にする。逃げられない構造。",
    },
    "competition": {
        "label":    "競争",
        "desc":     "同じ目標を奪い合う。尊敬と憎悪が同居する拮抗関係。",
        "drama":    "相手を超えたい欲望と相手に超えてほしい矛盾",
        "dark_side": "競争が相手の破滅を望む憎悪に転化する。",
    },
    "salvation": {
        "label":    "救済",
        "desc":     "一方が他方を「救う」という使命感・義務感。相手の痛みを癒したい衝動。",
        "drama":    "救う側の傲慢さ・救われる側の誇りとの衝突",
        "dark_side": "救済が相手の自己決定を奪う。「救ってあげる」という支配。",
    },
    "exploitation": {
        "label":    "搾取",
        "desc":     "一方が他方の能力・感情・存在を利用する。意図的または無自覚な消費。",
        "drama":    "搾取と気づく瞬間の激しい感情・それでも離れられない理由",
        "dark_side": "搾取が愛情に偽装される。気づけない構造。",
    },
    "surrogate_family": {
        "label":    "代替親子",
        "desc":     "血縁なき親子関係。欠落した家族の穴を互いに埋めようとする。",
        "drama":    "「親子」という関係が恋愛・友情・対立に転化するとき",
        "dark_side": "代替関係が本物の関係形成を阻害する。成長の停止。",
    },
    "surveillance": {
        "label":    "監視",
        "desc":     "一方が他方を常に観察・管理する。知ることへの渇望と支配衝動。",
        "drama":    "「見られている」安心と恐怖・監視が愛情の歪んだ形である暴露",
        "dark_side": "監視が相手の自由を完全に奪う。愛の名の下の支配。",
    },
    "mutual_support": {
        "label":    "相互支援",
        "desc":     "弱点を補い合う対等な支え合い。一方的でない双方向の支持。",
        "drama":    "「支え合い」が崩れる瞬間・どちらかが強くなりすぎたとき",
        "dark_side": "相互依存への転化。自立できなくなる共依存。",
    },
    "solitude_sharing": {
        "label":    "孤立共有",
        "desc":     "それぞれが孤独だが、共にいることで孤独が癒える。「この人と一緒なら」という唯一性。",
        "drama":    "孤独が解消されることへの恐怖・「消えてしまう前に」という焦燥",
        "dark_side": "孤独の解消が相手への執着・所有欲に転化する。",
    },
    # ── ここに新項目を追加 ────────────────────────────────────
    # 例:
    # "rivalry_love": {
    #     "label":    "恋敵",
    #     "desc":     "同じ相手を愛する者同士の複雑な引力。",
    #     ...
    # },
}

# VR_LABELS は Vタイプ廃止により削除済み


# get_vr_top_items は Vタイプ廃止により削除済み


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s1":  base / "s01_plot_twist"   / f"s01_twist_latest_{novel_type}.md",
        "s3":  base / "s03_age_design"   / f"s03_age_latest_{novel_type}.md",
        "s4":  base / "s04_age_gap"      / f"s04_age_gap_latest_{novel_type}.md",
        "s5":  base / "s05_gender_design"/ f"s05_gender_latest_{novel_type}.md",
    }
    limits = {"s1": 1500, "s3": 1500, "s4": 1500, "s5": 1500}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""
            print(f"  [INFO] {key.upper()}出力: なし")

    # S2 JSON
    s2j = base / "s02_submission" / f"s02_params_latest_{novel_type}.json"
    results["s2_params"] = {}
    if s2j.exists():
        with open(s2j, encoding="utf-8") as f:
            results["s2_params"] = json.load(f)
        print(f"  [INFO] S2パラメータ: 読み込み済み")

    return results


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(main_key: str, sub_key: str,
                 twist_key: str, prev: dict,
                 contest_key: str) -> str:

    weights      = prev["s2_params"].get("weights", {})
    contest_name = prev["s2_params"].get("contest_name", contest_key or "未設定")

    # 全項目の親和スコア表を生成
    score_map = {"◎": 3, "○": 2, "△": 1, "×": 0}
    items_table = "| 項目 | ラベル | 暗黒面 |\n|-----|------|------|\n"
    for k, v in GRAVITY_ITEMS.items():
        items_table += f"| {k} | {v['label']} | {v['dark_side'][:20]}… |\n"

    # 主軸・副軸の詳細
    def item_detail(key: str, role: str) -> str:
        if key == "auto" or key not in GRAVITY_ITEMS:
            return f"【{role}：AI自動選定】\n上記テーブルからS1〜S5を踏まえて最適な項目を選んでください。\n"
        item = GRAVITY_ITEMS[key]
        return (
            f"【{role}：{item['label']}】\n"
            f"概要：{item['desc']}\n"
            f"生まれるドラマ：{item['drama']}\n"
            f"暗黒面：{item['dark_side']}\n"
        )

    # autoモード時のVR推奨項目
    # fix7: Vタイプ廃止対応 - twist_keyをautoモードのヒントに使用
    auto_hint = ""
    if main_key == "auto" or sub_key == "auto":
        twist_label = f"【S1どんでん返しパターン：{twist_key}】" if twist_key else ""
        auto_hint = f"\n{twist_label}\nS1〜S5の設計を踏まえて最適な重力項目を主軸・副軸に選んでください。\n"

    return f"""あなたはこの小説作品の「関係性重力設計者」です。
以下の情報を基に、主人公と相方の関係性を支配する「重力」を設計してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【関係性重力 全項目テーブル（v1.0 / 11項目）】
{items_table}
{auto_hint}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

{item_detail(main_key, "主軸重力")}
{item_detail(sub_key,  "副軸重力")}

【S2 6軸パラメータ】
感情刺激度:{weights.get("emotion","?")} / 文学性:{weights.get("literary","?")} / キャラ魅力度:{weights.get("character","?")}

【S1どんでん返し構造（抜粋）】
{prev["s1"]}

【S5性別・炸点・熱量設計（抜粋）】
{prev["s5"]}

【S4年齢差設計（抜粋）】
{prev["s4"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

# 関係性重力設計書（S06）

---

## ■ 関係性重力の確定

**主軸重力：**（項目名・ラベル）
**副軸重力①：**（項目名・ラベル）
**副軸重力②（任意）：**
**autoモードの場合は選定理由：**

**この組み合わせが生む関係性の核心（1文）：**

---

## ■ 主軸重力の詳細設計

**序盤での現れ方：**（読者に何として見えるか）
**中盤での強化：**（何をきっかけに重力が強まるか）
**どんでん返しとの接続：**（転で重力がどう機能するか）
**暗黒面の顕在化タイミング：**（物語の何%地点で・どう表れるか）
**暗黒面をテーマとして描くか / 回避するか：**

---

## ■ 副軸重力の詳細設計

**副軸①の役割：**（主軸を強化する / 対比する / 補完する）
**主軸×副軸の相互作用：**（この2つが合わさることで生まれるドラマ）
**副軸②がある場合：**

---

## ■ S5炸点との連動

S5で設計した炸点と重力の接続を設計してください。

| 炸点 | 主軸重力の動き | 副軸重力の動き | 熱量変化 |
|-----|------------|------------|:------:|
| 炸点① | | | |
| 炸点② | | | |
| 炸点③（クライマックス） | | | |

---

## ■ どんでん返し構造との接続

**どんでん返し前：読者が思い込む重力の形：**
（表面的にはどの重力に見えるか）

**どんでん返し後：真の重力の形：**
（実はこの重力だったという「意味の書き換え」）

**パラダイム・シフトの瞬間：**
（重力の再解釈が起きる具体的な場面）

---

## ■ 重力の成長曲線

この関係性が物語を通じてどう変化するか：

**序盤（0〜25%）：**
**承（25〜75%）：**
**転・結（75〜100%）：**
**エピローグでの残像：**（解決後も残る重力の痕跡）

---

## ■ S7（哲学的問い設計）への引き渡しパラメータ

**この重力から生まれる哲学的問いの種（3つ）：**
  問い①（主軸重力から）：
  問い②（暗黒面から）：
  問い③（どんでん返し構造×重力から）：

**S7で深化させるべき核心：**
（この重力設計を踏まえた「問い」の方向性）
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
    main_key    = config.get("gravity_main", "auto")
    sub_key     = config.get("gravity_sub",  "auto")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    # キーのバリデーション
    valid_keys = list(GRAVITY_ITEMS.keys()) + ["auto"]
    if main_key not in valid_keys:
        print(f"  [WARN] 不明なgravity_main: {main_key} → autoに変更")
        main_key = "auto"
    if sub_key not in valid_keys:
        print(f"  [WARN] 不明なgravity_sub: {sub_key} → autoに変更")
        sub_key = "auto"

    print("\n[S6] 関係性重力設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  主軸: {GRAVITY_ITEMS[main_key]['label'] if main_key != 'auto' else 'AI自動選定'}")
    print(f"  副軸: {GRAVITY_ITEMS[sub_key]['label']  if sub_key  != 'auto' else 'AI自動選定'}")
    print(f"  項目数: {len(GRAVITY_ITEMS)}項目（拡張可能）")

    # ── 前ステップ出力読み込み ────────────────
    prev = load_prev_outputs(novel_type)

    # ── fix4: twist_key 抽出（Vタイプ廃止対応） ────────────────
    twist_key = ""
    for line in prev["s1"].split("\n"):
        if "どんでん返しパターン：" in line:
            parts = line.split("：", 1)
            if len(parts) > 1:
                twist_key = parts[1].strip()
            break
    if twist_key:
        print(f"  [INFO] S1パターン: {twist_key}")

    # ── Claude Sonnet で設計 ────────────────
    prompt = build_prompt(main_key, sub_key, twist_key, prev, contest_key)
    print("  関係性重力設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    suffix = f"{main_key}_x_{sub_key}"
    content = f"""# 関係性重力設計
実行日時：{timestamp}
小説タイプ：{novel_type}
主軸：{main_key}（{GRAVITY_ITEMS.get(main_key, {}).get("label", "AI選定")}）
副軸：{sub_key}（{GRAVITY_ITEMS.get(sub_key,  {}).get("label", "AI選定")}）
コンテスト：{contest_key or "未設定"}
項目バージョン：v1.0 / {len(GRAVITY_ITEMS)}項目

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s06_{novel_type}_{suffix}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s06_gravity_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        main_label = GRAVITY_ITEMS.get(main_key, {}).get("label", "AI選定")
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_関係性重力設計_{main_label}")},
            "スキル":     {"rich_text": txt("S6_関係性重力設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "関係性重力設計", result)

    print("[S6] 完了\n")
    print("  次のステップ: S7（哲学的問い設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 7 --type {novel_type}")

    return {
        "gravity_main":  main_key,
        "gravity_sub":   sub_key,
        "twist_key":     twist_key,
        "result":        result,
        "timestamp":     timestamp,
    }


if __name__ == "__main__":
    import argparse
    valid = list(GRAVITY_ITEMS.keys()) + ["auto"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--gravity-main", default="auto", choices=valid,
                        help="主軸重力項目（省略時: auto→AI選定）")
    parser.add_argument("--gravity-sub",  default="auto", choices=valid,
                        help="副軸重力項目（省略時: auto→AI選定）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"]    = args.type
    _config["gravity_main"]  = args.gravity_main
    _config["gravity_sub"]   = args.gravity_sub
    _config["contest"]       = args.contest
    run(config=_config)
