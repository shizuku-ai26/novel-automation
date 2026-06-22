# -*- coding: utf-8 -*-
"""
S7：哲学的問い設計スキル
呼び出し：python run_pipeline.py --skill 7 --type short
役割：S1（価値観反転）とS6（関係性重力）が出力した「問いの種」を
     合流・深化させ、作品のOSとなる哲学的問いを確定する。
     「テーマ（主張）」ではなく「問い（揺らぎ）」を設計する。

出力：
  ・核心の問い（1本・作品を貫く最重要の問い）
  ・補助の問い（2〜3本・核心を多角的に支える問い）
  ・S8（感情設計）へのパラメータ
  ・S9（テーマ設計）へのパラメータ

config.yaml 対応パラメータ:
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

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s07_philosophy"


# ============================================================
# 問いの強度チェックリスト（プロンプト内で参照）
# ============================================================

QUESTION_STRENGTH = """
【強い問いの条件】
✅ Yes/Noで答えられない
✅ 答えが物語の進行によって変わる
✅ 読者自身の経験と接続できる
✅ 登場人物が「体で答える」（行動で問いに向き合う）
✅ どんでん返し後に問いの意味が書き換わる
✅ 読後も答えが出ないまま残る

【弱い問いの例（避けるべき）】
❌ 「愛とは何か」→ 抽象的すぎて登場人物が体現できない
❌ 「正義は存在するか」→ 主張になっている
❌ 「人は一人では生きられない」→ 答えが先に見えている
❌ 「友情の大切さ」→ テーマであって問いではない

【強い問いの例】
✅ 「偽物の記憶でも、愛は成立するか？」
✅ 「守ることと支配することの境界線はどこにあるか？」
✅ 「相手が望む自分を演じ続けた先に、本当の自分は残るか？」
✅ 「消えることが最後の愛になりうるか？」
✅ 「善意で誰かを壊したとき、それは罪か？」
"""

# V1〜V7 × 問いの方向性
VR_QUESTION_DIRECTIONS = {
    "V1": "善意・救済・保護がどこで支配・搾取に転化するか",
    "V2": "愛・献身・絆がどこで洗脳・依存・鎖に転化するか",
    "V3": "加害者と被害者の境界線はどこにあるか",
    "V4": "正義・秩序・罰がどこで暴力・支配に転化するか",
    "V5": "記憶・真実・幸福の優先順位はどう決まるか",
    "V6": "目的・手段・達成の関係がどう逆転するか",
    "V7": "存在すること・消えることの意味と責任",
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s1": base / "s01_plot_twist"    / f"s01_twist_latest_{novel_type}.md",
        "s2": base / "s02_submission"    / f"s02_submission_latest_{novel_type}.md",
        "s5": base / "s05_gender_design" / f"s05_gender_latest_{novel_type}.md",
        "s6": base / "s06_gravity"       / f"s06_gravity_latest_{novel_type}.md",
    }
    limits = {"s1": 1500, "s2": 600, "s5": 400, "s6": 1200}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""
            print(f"  [INFO] {key.upper()}出力: なし")

    return results


def extract_vr_key(s1_text: str) -> str:
    for line in s1_text.split("\n"):
        for v in ["V1", "V2", "V3", "V4", "V5", "V6", "V7"]:
            if v in line:
                return v
    return ""


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(prev: dict, vr_key: str, novel_type: str,
                 contest_key: str, tone_mode: str = "casual") -> str:

    vr_direction = VR_QUESTION_DIRECTIONS.get(vr_key, "")
    contest_note = ""
    if contest_key == "note":
        contest_note = "※note創作大賞：問いは感情と直結させる。読者が「自分のこと」として受け取れる問いに。"
    elif contest_key == "kakugawa_chara":
        contest_note = "※角川文庫キャラ：問いはキャラクターの行動から自然に浮かび上がるものに。"
    elif contest_key == "kakuyomu":
        contest_note = "※カクヨムコン：問いは明示せず、読者がエンタメを楽しむ中で自然に感じる程度に。"
    elif contest_key == "everystory":
        contest_note = "※エブリスタ：問いは感情爆発のシーンに溶け込ませる。哲学的に語らない。"

    tone_note = (
        "【tone_mode: casual】\n"
        "この作品は単発・カジュアル向けです。\n"
        "・答えがわかりやすい普遍的な問いを設計する\n"
        "  例：「本当の友情とは何か」「失敗から成長できるか」「本物の気持ちを伝える勇気とは」\n"
        "・答えが人によって変わる難解な問いは避ける\n"
        "・読後に「なるほど」と納得できる問いにする"
    ) if tone_mode == "casual" else (
        "【tone_mode: hard】\n"
        "この作品は文学的・ハード向けです。\n"
        "・答えが人によって変わる難解な問いを設計する\n"
        "  例：「本物の怒りは本当に自分のものか」「善意の支配は悪意の支配より軽いか」\n"
        "・読後に読者に問いかけ続ける余韻を持たせる"
    )

    return f"""あなたはこの小説作品の「哲学的問い設計者」です。

{tone_note}

S1・S6が出力した問いの種を合流・深化させ、
この作品のOSとなる哲学的問いを確定してください。

{QUESTION_STRENGTH}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S1価値観反転の問いの種（既出）】
{prev["s1"]}

【S1 VR{vr_key}の問いの方向性】
{vr_direction}

【S6関係性重力の問いの種（既出）】
{prev["s6"]}

【S5炸点・熱量設計（参考）】
{prev["s5"]}

【S2投稿形態（参考）】
{prev["s2"]}

{contest_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

## ■ 核心の問い（1本）

**問い：**
（「〜か？」で終わる1文。20〜40文字目安）

**この問いが「強い」理由：**
（強い問いの条件のうち、どれを満たしているか）

**登場人物がこの問いに「体で答える」場面：**
（どのシーン・行動でこの問いに向き合うか）

**どんでん返し前後で問いの意味がどう変わるか：**

**読後に読者の胸に何が残るか：**

---

## ■ 補助の問い（2〜3本）

### 補助①
**問い：**
**役割：**（核心の問いをどう支えるか・補完/対比/深化のどれか）
**登場人物との接続：**（誰がこの問いを体現するか）

### 補助②
**問い：**
**役割：**
**登場人物との接続：**

### 補助③（任意）
**問い：**
**役割：**
**登場人物との接続：**

---

## ■ 問いの構造設計

**核心の問いが物語に「埋め込まれる」3つの方法：**
（説明せずに問いを伝えるための具体的な描写・シーン・台詞の設計）
  方法①：
  方法②：
  方法③：

**「問いを語らせない」ための禁止事項：**
（登場人物に問いを直接語らせないためのルール）

---

## ■ 問いと感情の接続

**核心の問いが最も強く響く「感情の瞬間」：**
（どの感情状態のときに問いが読者の胸に刺さるか）

**S5の炸点③（クライマックス）での問いの爆発：**
（クライマックスでこの問いがどのように爆発するか）

**読後感との接続：**
（この問いが残ることで読者にどんな読後感が生まれるか）

---

## ■ S8（感情設計）への引き渡しパラメータ

**この問いが最も強く機能する感情タイプ（推奨）：**
（喪失 / 浄化 / 不穏 / 畏怖 / 虚無 / 希望 / 怒り / 罪悪感 のどれか）

**読後感として固定すべき感情：**
（物語が終わったとき読者に残したい感情を1〜2個）

**感情が「説明」にならないための指針：**
（この問いをどう「行動・身体描写」に変換するか）

---

## ■ S9（テーマ設計）への引き渡しパラメータ

**問いからテーマへの変換（禁止パターン）：**
（この問いが「主張」に堕落しやすい表現を列挙）
例：「愛は記憶を超える」→ 答えを言ってしまっている

**テーマが「揺らぎ」を保つための条件：**
（物語を通じて答えが一方向に収束しないための設計）

**主人公とサブキャラが問いに対して「異なる答え」を体現する設計：**
（誰がどの立場から問いに向き合うか）
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

    print("\n[S7] 哲学的問い設計スキル 開始")
    tone_mode = config.get("tone_mode", None)
    if tone_mode not in ("casual", "hard"):
        tone_mode = "casual" if novel_type in ("short", "medium") else "hard"
    print(f"  小説タイプ: {novel_type}")
    print(f"  tone_mode: {tone_mode}")

    # ── 前ステップ出力読み込み ────────────────
    prev   = load_prev_outputs(novel_type)
    vr_key = extract_vr_key(prev["s1"])
    if vr_key:
        print(f"  VRタイプ: {vr_key} / 問いの方向: {VR_QUESTION_DIRECTIONS.get(vr_key,'')[:30]}...")

    # ── Claude Sonnet で設計 ────────────────
    prompt = build_prompt(prev, vr_key, novel_type, contest_key, tone_mode)
    print("  哲学的問い設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    content = f"""# 哲学的問い設計
実行日時：{timestamp}
小説タイプ：{novel_type}
VRタイプ：{vr_key or "未設定"}
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s07_{novel_type}_{vr_key or 'noVR'}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s07_philosophy_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_哲学的問い設計_{vr_key}")},
            "スキル":     {"rich_text": txt("S7_哲学的問い設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "哲学的問い設計", result)

    print("[S7] 完了\n")
    print("  次のステップ: S8（感情設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 8 --type {novel_type}")

    return {
        "vr_key":    vr_key,
        "result":    result,
        "timestamp": timestamp,
    }


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
