# -*- coding: utf-8 -*-
"""
S5：主人公と相方の性別・炸点・熱量設計スキル
呼び出し：python run_pipeline.py --skill 5 --type short
役割：旧pairing4択を核に、関係性の「炸点（爆発する瞬間）」と
     「熱量（感情強度の推移）」を設計する。
     S6（関係性重力設計）へのパラメータを引き渡す。

config.yaml 対応パラメータ:
  pairing: "male-female" / "female-male" / "male-buddy" / "female-buddy" / 省略（AI推奨）
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

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s05_gender_design"


# ============================================================
# 旧pairing 4択定義（拡張版）
# ============================================================

PAIRING_TYPES = {
    "male-female": {
        "label":     "男主人公×女相方",
        "desc":      "王道。相方は主人公の価値を見抜く存在。理解＋対等の両立が現代最強。",
        "structure": "自己肯定回復装置。尊敬・会話テンポ・支え合いが必要。",
        "heat_base": 80,
        "sparks": [
            "相方だけが主人公の「本当の弱さ」を見抜く瞬間",
            "主人公が相方のために初めて誰かのために動く瞬間",
            "相方が「守られる側」から「守る側」に転じる瞬間",
        ],
        "heat_curve": "序盤：緊張と距離感 → 中盤：信頼の積み上げ → 転：感情爆発 → 結：選択の重み",
        "contest_fit": {
            "note":           "◎ 現代読者の共感ど真ん中",
            "kakugawa_chara": "◎ 王道・最も実績がある",
            "kakuyomu":       "◎ 異世界・現代問わず最強",
            "everystory":     "◎ コミカライズの定番",
        },
    },
    "female-male": {
        "label":     "女主人公×男相方",
        "desc":      "男相方は察する・尊重する・弱さを見せられる感情処理能力が重要。対等な精神戦。",
        "structure": "女性向け・一般文芸寄り。支配・上下構造は避ける。",
        "heat_base": 75,
        "sparks": [
            "男相方が主人公の「できない部分」を責めずに受け入れる瞬間",
            "主人公が男相方の前でだけ弱さを見せる瞬間",
            "男相方が「尊重」から「選択」に転じる瞬間（好きだから引く→好きだから踏み込む）",
        ],
        "heat_curve": "序盤：観察と距離感 → 中盤：信頼の試験 → 転：弱さの開示 → 結：対等な選択",
        "contest_fit": {
            "note":           "◎ note読者層（20〜30代女性）に最適",
            "kakugawa_chara": "○ 一般文芸寄りで角川にも実績あり",
            "kakuyomu":       "△ 女主人公は設定強化が必要",
            "everystory":     "◎ 女性向け恋愛で強い",
        },
    },
    "male-buddy": {
        "label":     "男×男バディ",
        "desc":      "信頼の獲得が本質。行動で関係が積み上がる。言葉より背中。無言で助ける・命を預ける。",
        "structure": "正反対バディ/ライバル型/相互依存型。軽口・挑発・戦術会話が特徴。",
        "heat_base": 70,
        "sparks": [
            "言葉ではなく「行動」で信頼を証明する瞬間",
            "互いの「一番見せたくない部分」を目撃してしまう瞬間",
            "どちらかが相手のために命を賭ける瞬間",
        ],
        "heat_curve": "序盤：軽口と反発 → 中盤：戦場での信頼 → 転：命を預ける選択 → 結：言葉なき絆",
        "contest_fit": {
            "note":           "△ note読者層にはやや届きにくい",
            "kakugawa_chara": "◎ バディ・お仕事系で強い",
            "kakuyomu":       "◎ バトル・冒険系で王道",
            "everystory":     "○ 設定次第で漫画映えする",
        },
    },
    "female-buddy": {
        "label":     "女×女バディ",
        "desc":      "感情共有が本質。この人だけ分かってくれる共感型が非常に強い。会話・心情共有・感情の変化。",
        "structure": "共感型/対照型/共依存型。空気・距離感・言葉の温度が重要。",
        "heat_base": 75,
        "sparks": [
            "「この人だけが分かってくれる」と気づく瞬間",
            "互いの「秘密」を共有してしまう瞬間",
            "一方が傷ついたとき、もう一方が怒りを見せる瞬間",
        ],
        "heat_curve": "序盤：表面的な共感 → 中盤：秘密の共有 → 転：片方の危機 → 結：選んだ理由",
        "contest_fit": {
            "note":           "◎ note読者層に非常に刺さる",
            "kakugawa_chara": "○ 居場所系・お仕事系で機能する",
            "kakuyomu":       "△ 設定強化が必要",
            "everystory":     "◎ 女性向け感情爆発で強い",
        },
    },
    "male-neutral": {
        "label":     "男主人公×中性/性別不明の相方",
        "desc":      "相方は性別を持たない・超越した存在（怪物・精霊・異種族など）。"
                     "性別的な引力を排除し、純粋な「存在としての絆」と「守ることの意味」を描く。",
        "structure": "保護→共生→解放型。主人公の「守りたい」という衝動が「尊重したい」へと変化する。"
                     "相方の意思・選択・帰還が物語の重力になる。",
        "heat_base": 65,
        "sparks": [
            "「守りたい」という衝動が「この存在の意思を尊重したい」に変わる瞬間",
            "相方が言語ではない方法（身体・沈黙・存在感）で主人公に何かを伝える瞬間",
            "相方が初めて「主体的な選択」を下し、主人公がそれを止めないことを選ぶ瞬間",
        ],
        "heat_curve": "序盤：一方向の保護と不思議 → 中盤：翻訳不可能な共鳴の蓄積 → 転：相方の意思の発現 → 結：解放という形の愛",
        "contest_fit": {
            "note":           "◎ 非恋愛×深い感情線はnote読者層に強い。拡散力が高い",
            "kakugawa_chara": "○ 設定の独自性が高く差別化できる",
            "kakuyomu":       "○ 異種族・怪物系との親和性が高い",
            "everystory":     "○ 感情爆発シーンを丁寧に設計すれば機能する",
        },
    },
    "female-neutral": {
        "label":     "女主人公×中性/性別不明の相方",
        "desc":      "相方は性別を持たない・超越した存在（怪物・精霊・異種族など）。"
                     "女主人公が「守ること」に向ける感情（保護・共感・姉的愛着）を通じて、"
                     "「守ることが支配になる瞬間」を描く。",
        "structure": "共感型保護→解放型。女主人公の感情解像度の高さが相方の「言語化できない意思」を読み取る役割を担う。"
                     "恋愛に回収されない純粋な情愛関係として機能する。",
        "heat_base": 70,
        "sparks": [
            "女主人公が相方の「言葉にならない感情」を初めて正確に読み取る瞬間",
            "守ることと縛ることが同一だったと気づく瞬間の静かな痛み",
            "相方が帰還を選んだとき、主人公が「行って」と言える瞬間",
        ],
        "heat_curve": "序盤：保護本能と不思議な共鳴 → 中盤：相方への愛着と組織Aへの依存が交差 → 転：守る意味の崩壊 → 結：手放すことが愛だった",
        "contest_fit": {
            "note":           "◎ note女性読者層に直撃する。感情の純度と独自性で差別化できる",
            "kakugawa_chara": "◎ 女主人公×異質な存在との絆は角川でも実績がある",
            "kakuyomu":       "○ 異種族・怪物系の設定強度があれば機能する",
            "everystory":     "◎ 感情爆発と純粋な愛の形でコミカライズ映えする",
        },
    },
}

# 熱量レベル定義（0〜100）
HEAT_LEVELS = {
    (0,  30): "冷静・理性的。感情より思考が先行する関係。",
    (31, 50): "穏やか。信頼ベースの安定した関係。",
    (51, 70): "温かみがある。感情が動くが爆発はしない。",
    (71, 85): "熱い。感情が表面に出やすく炸点が多い。",
    (86, 100): "灼熱。感情が常に臨界点近くにある関係。",
}

def get_heat_desc(level: int) -> str:
    for (lo, hi), desc in HEAT_LEVELS.items():
        if lo <= level <= hi:
            return desc
    return ""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    # S1
    s1 = base / "s01_plot_twist" / f"s01_twist_latest_{novel_type}.md"
    results["s1"] = s1.read_text(encoding="utf-8")[:1500] if s1.exists() else ""

    # S2 JSON
    s2j = base / "s02_submission" / f"s02_params_latest_{novel_type}.json"
    results["s2_params"] = {}
    if s2j.exists():
        with open(s2j, encoding="utf-8") as f:
            results["s2_params"] = json.load(f)

    # S3
    s3 = base / "s03_age_design" / f"s03_age_latest_{novel_type}.md"
    results["s3"] = s3.read_text(encoding="utf-8")[:1500] if s3.exists() else ""

    # S4
    s4 = base / "s04_age_gap" / f"s04_age_gap_latest_{novel_type}.md"
    results["s4"] = s4.read_text(encoding="utf-8")[:1500] if s4.exists() else ""

    # 読み込み状況を表示
    for k in ["s1", "s3", "s4"]:
        label = {"s1": "S1", "s3": "S3", "s4": "S4"}[k]
        status = "読み込み済み" if results[k] else "なし"
        print(f"  [INFO] {label}出力: {status}")
    if results["s2_params"]:
        print(f"  [INFO] S2パラメータ: 読み込み済み")

    return results


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(pairing_key: str, pairing_info: dict,
                 prev: dict, contest_key: str,
                 twist_key: str = "", novel_type: str = "short") -> str:

    weights   = prev["s2_params"].get("weights", {})
    contest_name = prev["s2_params"].get("contest_name", contest_key or "未設定")
    emotion_w = weights.get("emotion", 70)

    # 熱量ベース値（S2感情刺激度で補正）
    heat_base  = pairing_info["heat_base"]
    heat_adj   = heat_base + int((emotion_w - 70) * 0.3)
    heat_adj   = max(0, min(100, heat_adj))
    heat_desc  = get_heat_desc(heat_adj)

    # コンテスト相性
    contest_fit = ""
    if contest_key:
        fit = pairing_info["contest_fit"].get(contest_key, "")
        contest_fit = f"【{pairing_info['label']}×{contest_name}の相性】{fit}"

    # どんでん返しパターン情報（s1_fit は廃止済み）
    twist_info = f"【S1どんでん返しパターン：{twist_key}】" if twist_key else ""

    # autoモード指示
    auto_instruction = ""
    if pairing_key == "auto":
        all_types = "\n".join(
            f"・{k}: {v['label']} ── {v['desc']}"
            for k, v in PAIRING_TYPES.items()
        )
        auto_instruction = f"""
【autoモードの指示】
S1〜S4の情報から最適なpairingタイプを1つ選んでください。
選択肢：
{all_types}
選定理由も必ず説明してください。
"""

    sparks_text = "\n".join(
        f"  炸点例{i+1}: {s}"
        for i, s in enumerate(pairing_info["sparks"])
    )

    return f"""あなたはこの小説作品の「性別・関係性熱量設計者」です。
以下の情報を基に、主人公と相方の性別構造と関係性の炸点・熱量を設計してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【選択されたペアリングタイプ】
{pairing_info["label"]}
概要：{pairing_info["desc"]}
関係構造：{pairing_info["structure"]}

【熱量ベース値】
基準熱量: {heat_base}/100
S2感情刺激度({emotion_w})補正後: {heat_adj}/100
熱量の質: {heat_desc}

【このタイプの炸点例（参考）】
{sparks_text}

【熱量推移の基本曲線】
{pairing_info["heat_curve"]}

{contest_fit}
{twist_info}

【S2 6軸パラメータ】
感情刺激度:{emotion_w} / キャラ魅力度:{weights.get("character","?")} / 文学性:{weights.get("literary","?")}

【S1どんでん返し構造（抜粋）】
{prev["s1"]}

【S3主人公年齢設計（抜粋）】
{prev["s3"]}

【S4年齢差設計（抜粋）】
{prev["s4"]}

{auto_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

# 性別・炸点・熱量設計書（S05）

---

## ■ ペアリングの確定

**タイプ：** {pairing_info["label"]}
**主人公の性別：**
**相方の性別：**
**autoモードの場合は選定理由：**

---

## ■ 熱量設計

**熱量レベル（確定値）：** {heat_adj}/100
**熱量の質：** {heat_desc}

**熱量推移（この作品固有）：**
| フェーズ | 熱量 | 状態 | きっかけ |
|---------|:---:|------|---------|
| 序盤（0〜25%） | /100 | | |
| 承前半（25〜50%） | /100 | | |
| ミッドポイント（50%） | /100 | | |
| 承後半（50〜75%） | /100 | | |
| 転・クライマックス（75〜100%） | /100 | | |

**最高熱量の瞬間：**（物語のどの場面で熱量が頂点になるか）
**熱量が最も下がる瞬間：**（どん底・距離感が最大になる瞬間）

---

## ■ 炸点設計（この作品固有）

炸点とは「関係性が爆発・変質する瞬間」です。
この作品固有の炸点を3〜5個設計してください。

**炸点①（序盤）：**
・場面：
・何が爆発するか：（感情の種類）
・S1どんでん返し構造との接続：
・読者が感じる感情：

**炸点②（中盤）：**
・場面：
・何が爆発するか：
・熱量への影響：（上昇/下降/急落/急上昇）
・読者が感じる感情：

**炸点③（転・クライマックス）：**
・場面：
・何が爆発するか：
・これがどんでん返しとどう絡むか：
・読者が感じる感情：

**炸点④（任意・追加）：**
**炸点⑤（任意・追加）：**

---

## ■ 性別構造が生む固有のドラマ

**このペアリングだからこそ描ける葛藤：**
**このペアリングだからこそ言えない言葉：**
**このペアリングで陥りやすいステレオタイプ：**（回避すべきパターン）
**ステレオタイプを回避する具体的な工夫：**

---

## ■ S1どんでん返し構造との接続

**どんでん返しパターン（{twist_key or "未設定"}）がこのペアリングでどう機能するか：**
**炸点③（クライマックス）でどんでん返しがどう爆発するか：**

---

## ■ コンテスト適性評価

**投稿先：** {contest_name}
**このペアリングの適性：** {contest_fit if contest_fit else "（コンテスト未設定）"}
**炸点設計でコンテストに合致するポイント：**
**このペアリングでありがちなコンテストNG：**（回避すべき型）

---

## ■ S6（関係性重力設計）への引き渡しパラメータ

**確定ペアリング：** {pairing_info["label"]}
**確定熱量レベル：** {heat_adj}/100
**最大炸点の場面：**
**S6で深化させるべき関係性の核心：**
（保護・依存・崇拝・共犯・競争・救済・搾取・代替親子・監視のどれが最も強く機能するか）
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
    pairing_key = config.get("pairing", "auto")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    if pairing_key not in PAIRING_TYPES:
        pairing_key = "auto"

    print("\n[S5] 性別・炸点・熱量設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    # ── 前ステップ出力読み込み ────────────────
    prev = load_prev_outputs(novel_type)

    # ── pairing の確定 ────────────────────────
    if pairing_key == "auto":
        pairing_info = {
            "label":     "自動選択（AIが4タイプから最適を選ぶ）",
            "desc":      "S1〜S4の情報から最適なタイプをAIが選定します。",
            "structure": "AIが設計",
            "heat_base": 75,
            "sparks":    ["AIが設計"],
            "heat_curve": "AIが設計",
            "contest_fit": {},
            "s1_fit": {},
        }
        print(f"  pairing: autoモード（AI推奨）")
    else:
        pairing_info = PAIRING_TYPES[pairing_key]
        print(f"  pairing: {pairing_info['label']}")

    # ── fix①: どんでん返しパターンをS1出力から抽出（Vタイプ廃止対応） ──
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
    prompt = build_prompt(
        pairing_key, pairing_info,
        prev, contest_key, twist_key, novel_type
    )
    print("  性別・炸点・熱量設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    content = f"""# 性別・炸点・熱量設計
実行日時：{timestamp}
小説タイプ：{novel_type}
ペアリング：{pairing_key}（{pairing_info["label"]}）
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s05_{novel_type}_{pairing_key}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s05_gender_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_性別炸点熱量設計_{pairing_info['label']}")},
            "スキル":     {"rich_text": txt("S5_性別炸点熱量設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "性別・炸点・熱量設計", result)

    print("[S5] 完了\n")
    print("  次のステップ: S6（関係性重力設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 6 --type {novel_type}")

    return {
        "pairing_key":   pairing_key,
        "pairing_label": pairing_info["label"],
        "result":        result,
        "timestamp":     timestamp,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--pairing", default="auto",
                        choices=["male-female", "female-male",
                                 "male-buddy", "female-buddy",
                                 "male-neutral", "female-neutral", "auto"],
                        help="ペアリングタイプ（省略時: auto→AI推奨）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"] = args.type
    _config["pairing"]    = args.pairing
    _config["contest"]    = args.contest
    run(config=_config)
