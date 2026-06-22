# -*- coding: utf-8 -*-
"""
S8：感情設計スキル
呼び出し：python run_pipeline.py --skill 8 --type short
役割：読後感を先に固定し、物語全体の感情波形を設計する。
     AI創作において最重要級のスキル。
     感情は「説明」ではなく「波形」として設計する。

出力：
  ・読後感の確定（1〜2個）
  ・感情波形（フェーズ別の感情推移）
  ・感情の「高低差」設計（緊張と弛緩）
  ・S9（テーマ設計）・S10（キャラ設計）へのパラメータ

config.yaml 対応パラメータ:
  emotion_ending: 読後感キー（省略時: S7出力から自動取得 / それもなければAI選定）
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

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s08_emotion"


# ============================================================
# 読後感 10項目定義
# ============================================================

EMOTION_ENDINGS = {
    "loss":       {
        "label":   "喪失",
        "desc":    "大切なものが消えた静かな痛み。涙より沈黙が残る。",
        "wave":    "穏やか→温かさの蓄積→大きな喪失→余韻の静寂",
        "contest": {"note": "◎", "kakugawa_chara": "○", "kakuyomu": "△", "everystory": "○"},
    },
    "catharsis":  {
        "label":   "浄化",
        "desc":    "涙とともに胸のつかえが取れる。泣いてよかったという感覚。",
        "wave":    "日常の重さ→感情の蓄積→一気の開放→清々しさ",
        "contest": {"note": "◎", "kakugawa_chara": "◎", "kakuyomu": "○", "everystory": "◎"},
    },
    "unease":     {
        "label":   "不穏",
        "desc":    "何かが解決していない違和感。世界への不信感が残る。",
        "wave":    "日常への疑い→不安の蓄積→反転→答えのない余韻",
        "contest": {"note": "○", "kakugawa_chara": "△", "kakuyomu": "△", "everystory": "△"},
    },
    "awe":        {
        "label":   "畏怖",
        "desc":    "人間や世界の大きさへの震え。自分の小ささを感じる。",
        "wave":    "日常→スケールの拡大→圧倒的な体験→自己の再認識",
        "contest": {"note": "△", "kakugawa_chara": "○", "kakuyomu": "○", "everystory": "△"},
    },
    "emptiness":  {
        "label":   "虚無",
        "desc":    "すべてが終わった後の空虚。意味を問い続ける沈黙。",
        "wave":    "目的の強度→全力の消費→達成後の空洞→問いの残滓",
        "contest": {"note": "○", "kakugawa_chara": "△", "kakuyomu": "△", "everystory": "△"},
    },
    "hope":       {
        "label":   "希望",
        "desc":    "困難の先に光が見える。続きを生きたくなる感覚。",
        "wave":    "困難の蓄積→どん底→小さな光→未来への一歩",
        "contest": {"note": "◎", "kakugawa_chara": "◎", "kakuyomu": "◎", "everystory": "○"},
    },
    "anger":      {
        "label":   "怒り",
        "desc":    "理不尽・不正義への燃える感情。読者が主人公に代わって怒る。",
        "wave":    "不公平の積み重ね→怒りの臨界→爆発→変化または敗北",
        "contest": {"note": "○", "kakugawa_chara": "○", "kakuyomu": "◎", "everystory": "◎"},
    },
    "guilt":      {
        "label":   "罪悪感",
        "desc":    "誰かを傷つけたことへの重さ。許しを求めながら許せない自分。",
        "wave":    "無自覚→気づき→自責の深化→赦しまたは抱えて生きる",
        "contest": {"note": "◎", "kakugawa_chara": "○", "kakuyomu": "△", "everystory": "○"},
    },
    "longing":    {
        "label":   "郷愁・切なさ",
        "desc":    "戻れない時間・場所・関係への甘い痛み。",
        "wave":    "幸福の記憶→現在との乖離→取り戻せない痛み→受容",
        "contest": {"note": "◎", "kakugawa_chara": "◎", "kakuyomu": "○", "everystory": "○"},
    },
    "exhilaration": {
        "label":   "高揚・爽快",
        "desc":    "やりきった達成感と興奮。体が震える熱さ。",
        "wave":    "困難の連続→限界突破→爆発的な達成→余韻の熱",
        "contest": {"note": "○", "kakugawa_chara": "○", "kakuyomu": "◎", "everystory": "◎"},
    },
    # ── 拡張ゾーン（必要に応じて追加） ────────────────────────
}


# ============================================================
# tone_mode別 推奨感情セット
# ============================================================

CASUAL_EMOTIONS = {
    "hope", "catharsis", "exhilaration", "longing"
}
# hope：困難の先に光が見える
# catharsis：泣いてよかったという感覚
# exhilaration：やりきった達成感
# longing：甘い切なさ・受容

HARD_EMOTIONS = {
    "guilt", "loss", "unease", "emptiness", "awe"
}
# guilt：罪悪感・許せない自分
# loss：静かな痛み
# unease：答えのない余韻
# emptiness：達成後の空洞
# awe：自分の小ささを感じる


def _get_tone_mode(config: dict) -> str:
    """tone_modeを取得。short/mediumは未指定時casual"""
    tone = config.get("tone_mode", None)
    if tone in ("casual", "hard"):
        return tone
    novel_type = config.get("novel_type", "short")
    if novel_type in ("short", "medium"):
        return "casual"
    return "hard"


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
        "s7": base / "s07_philosophy"    / f"s07_philosophy_latest_{novel_type}.md",
    }
    limits = {"s1": 400, "s2": 400, "s5": 400, "s6": 400, "s7": 1500}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""

    return results


def extract_emotion_from_s7(s7_text: str) -> list:
    """S7出力から推奨感情タイプを抽出する"""
    found = []
    keys = list(EMOTION_ENDINGS.keys())
    labels = {v["label"]: k for k, v in EMOTION_ENDINGS.items()}
    for line in s7_text.split("\n"):
        for label, key in labels.items():
            if label in line:
                if key not in found:
                    found.append(key)
        if len(found) >= 2:
            break
    return found


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(ending_keys: list, prev: dict,
                 contest_key: str, novel_type: str,
                 tone_mode: str = "casual") -> str:

    # 選択された読後感の詳細
    def ending_detail(key: str) -> str:
        if key not in EMOTION_ENDINGS:
            return f"【{key}：AI自動選定】"
        e = EMOTION_ENDINGS[key]
        return (
            f"【{e['label']}】\n"
            f"概要：{e['desc']}\n"
            f"基本波形：{e['wave']}\n"
            f"コンテスト適性：{e['contest'].get(contest_key, '─') if contest_key else '─'}\n"
        )

    endings_text = "\n".join(ending_detail(k) for k in ending_keys) if ending_keys \
        else "【AI自動選定】S7の推奨感情とS1〜S6の情報から最適な読後感を選んでください。"

    # 全10項目テーブル
    table = "| キー | ラベル | 概要 | コンテスト適性 |\n|-----|------|------|:-----------:|\n"
    for k, v in EMOTION_ENDINGS.items():
        fit = v["contest"].get(contest_key, "─") if contest_key else "─"
        table += f"| {k} | {v['label']} | {v['desc'][:20]}… | {fit} |\n"

    tone_note = (
        "【tone_mode: casual】\n"
        "単発・カジュアル向け作品です。\n"
        "・希望（hope）・浄化（catharsis）・高揚（exhilaration）・切なさ（longing）を優先\n"
        "・罪悪感・虚無・不穏は避ける\n"
        "・読後感は前向きで、読者が「読んでよかった」と感じる設計に"
    ) if tone_mode == "casual" else (
        "【tone_mode: hard】\n"
        "文学的・ハード向け作品です。\n"
        "・罪悪感（guilt）・喪失（loss）・不穏（unease）・虚無（emptiness）を積極的に使用\n"
        "・重く、読者に問いかける読後感を設計してよい"
    )

    return f"""あなたはこの小説作品の「感情設計者」です。
読後感を先に固定し、物語全体の感情波形を設計してください。

{tone_note}


重要思想：
・感情は「説明」ではなく「波形」として設計する
・感情を直接書かない（行動・身体描写・沈黙で表現する）
・高低差が大きいほど読者の没入度が上がる
・AI創作で最も平均化しやすい部分 → 意図的に設計する

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【読後感 全項目テーブル（{len(EMOTION_ENDINGS)}項目）】
{table}

【選択された読後感】
{endings_text}

【S7哲学的問い設計（抜粋）】
{prev["s7"]}

【S6関係性重力・S5炸点（抜粋）】
{prev["s6"]}
{prev["s5"]}

【S1価値観反転（抜粋）】
{prev["s1"]}

【S2投稿形態（参考）】
{prev["s2"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

## ■ 読後感の確定

**主読後感：**（キー名 + ラベル）
**副読後感（任意）：**
**autoモードの場合は選定理由：**

**読後感を「一文」で表現：**
（読み終わった読者が心の中でつぶやく言葉）

---

## ■ 感情波形設計

物語全体を通じた感情の推移を設計してください。

| フェーズ | 位置 | 支配的感情 | 強度(0-100) | きっかけ | 読者が感じること |
|---------|:---:|---------|:---------:|--------|--------------|
| プロローグ | 0-3% | | | | |
| 起（日常） | 3-15% | | | | |
| 非日常突入 | 15% | | | | |
| 承前半 | 15-50% | | | | |
| ミッドポイント | 50% | | | | |
| 承後半 | 50-75% | | | | |
| 転（どんでん返し） | 75% | | | | |
| 結（クライマックス） | 75-98% | | | | |
| エピローグ | 98-100% | | | | |

---

## ■ 感情の高低差設計

**最高点（感情強度MAX）：**
・位置（%）：
・感情の種類：
・具体的な場面：
・読者に与える体験：

**最低点（感情強度MIN・どん底）：**
・位置（%）：
・感情の種類：
・具体的な場面：
・この落差が読後感にどう機能するか：

**急落ポイント（感情が突然下がる瞬間）：**
（どんでん返しと連動する感情の急変を設計）

---

## ■ S5炸点との感情連動

| 炸点 | 直前の感情 | 炸点での感情爆発 | 直後の感情 | 波形への影響 |
|-----|---------|--------------|---------|----------|
| 炸点① | | | | |
| 炸点② | | | | |
| 炸点③（クライマックス） | | | | |

---

## ■ 感情を「説明しない」設計

**主読後感「{EMOTION_ENDINGS.get(ending_keys[0] if ending_keys else '', {}).get('label', '?')}」を身体描写で表現する方法（3例）：**
（「悲しかった」と書かずに悲しさを伝える具体的な描写例）
  例①：
  例②：
  例③：

**感情が「説明」になりやすい危険ゾーン（この作品固有）：**
（どのシーンで感情を直接書いてしまいがちか・回避策）

---

## ■ コンテスト別感情演出指針

**投稿先の感情演出ルール：**
（このコンテストで読者の感情を動かすために守るべき原則）

**冒頭3行での感情フック：**
（物語冒頭で読者の感情を掴む具体的な描写設計）

---

## ■ S9（テーマ設計）への引き渡しパラメータ

**この感情波形から導かれるテーマの「揺らぎ」：**
（感情の高低差がテーマの問いをどう強化するか）

**感情波形がテーマの「主張」に堕落しないための注意：**

## ■ S10（キャラクター設計）への引き渡しパラメータ

**主人公が体現すべき感情の変化曲線：**
（キャラ設計で必ず反映すべき感情の成長軌跡）

**相方キャラが主人公の感情を「引き出す」役割：**
（相方がいることで主人公のどの感情が表面化するか）
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

    print("\n[S8] 感情設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  感情項目数: {len(EMOTION_ENDINGS)}項目（拡張可能）")

    # ── 前ステップ出力読み込み ────────────────
    prev = load_prev_outputs(novel_type)

    # ── 読後感の決定 ─────────────────────────
    manual_key = config.get("emotion_ending", "")
    if manual_key and manual_key in EMOTION_ENDINGS:
        ending_keys = [manual_key]
        print(f"  読後感（手動指定）: {EMOTION_ENDINGS[manual_key]['label']}")
    elif prev["s7"]:
        ending_keys = extract_emotion_from_s7(prev["s7"])
        if ending_keys:
            labels = [EMOTION_ENDINGS[k]["label"] for k in ending_keys]
            print(f"  読後感（S7から自動取得）: {' / '.join(labels)}")
        else:
            ending_keys = []
            print("  読後感: AI自動選定")
    else:
        ending_keys = []
        print("  読後感: AI自動選定")

    # ── tone_mode取得 ──────────────────────
    tone_mode = _get_tone_mode(config)

    # ── Claude Sonnet で設計 ────────────────
    prompt = build_prompt(ending_keys, prev, contest_key, novel_type, tone_mode)
    print("  感情設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    suffix = "_".join(ending_keys) if ending_keys else "auto"
    content = f"""# 感情設計
実行日時：{timestamp}
小説タイプ：{novel_type}
読後感：{suffix}
コンテスト：{contest_key or "未設定"}
感情項目バージョン：v1.0 / {len(EMOTION_ENDINGS)}項目

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s08_{novel_type}_{suffix}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s08_emotion_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_感情設計_{suffix}")},
            "スキル":     {"rich_text": txt("S8_感情設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "感情設計", result)

    print("[S8] 完了\n")
    print("  次のステップ: S9（テーマ設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 9 --type {novel_type}")

    return {
        "ending_keys": ending_keys,
        "result":      result,
        "timestamp":   timestamp,
    }


if __name__ == "__main__":
    import argparse
    valid = list(EMOTION_ENDINGS.keys()) + [""]
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--emotion-ending", default="",
                        choices=list(EMOTION_ENDINGS.keys()) + [""],
                        help="読後感を手動指定（省略時: S7出力から自動取得→AI選定）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"]     = args.type
    _config["emotion_ending"] = args.emotion_ending
    _config["contest"]        = args.contest
    run(config=_config)
