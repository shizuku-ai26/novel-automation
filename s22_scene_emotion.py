# -*- coding: utf-8 -*-
"""
S22：シーン別感情設計スキル
呼び出し：python run_pipeline.py --skill 22 --type short
役割：物語全体の「感情波形」を章・シーン単位まで詳細化する。
     S8（全体感情設計）を受け取り、各シーンの感情強度と
     遷移を設計する。

重要思想：
  感情波形のパターン例：
    緊張→安心→違和感→喪失→静寂→反転
  
  プロットだけでは読者は没入しない。
  感情の高低差・速度・余韻が没入を生む。

次ステップ：S23（シーン別プロット設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s22_scene_emotion"


# ============================================================
# 感情タイプ定義（シーン単位）
# ============================================================

SCENE_EMOTIONS = {
    "tension":     {"label": "緊張",   "intensity_range": (6, 9),  "desc": "何かが起きる予感・不安・構え"},
    "relief":      {"label": "安心",   "intensity_range": (2, 5),  "desc": "脅威の解消・温かさ・緩み"},
    "unease":      {"label": "違和感", "intensity_range": (4, 7),  "desc": "何かがおかしい・不協和音"},
    "loss":        {"label": "喪失",   "intensity_range": (7, 10), "desc": "大切なものが消える瞬間"},
    "silence":     {"label": "静寂",   "intensity_range": (1, 4),  "desc": "感情の後の空白・余韻"},
    "reversal":    {"label": "反転",   "intensity_range": (8, 10), "desc": "価値観が書き換わる瞬間"},
    "warmth":      {"label": "温かさ", "intensity_range": (3, 6),  "desc": "人と人の距離が縮まる"},
    "exhilaration":{"label": "高揚",   "intensity_range": (7, 10), "desc": "アドレナリン・達成・爆発"},
    "despair":     {"label": "絶望",   "intensity_range": (7, 10), "desc": "どん底・希望の消滅"},
    "hope":        {"label": "希望",   "intensity_range": (5, 8),  "desc": "小さな光・前に進む力"},
    "guilt":       {"label": "罪悪感", "intensity_range": (5, 9),  "desc": "自分を責める・取り返しのなさ"},
    "curiosity":   {"label": "好奇心", "intensity_range": (3, 6),  "desc": "謎への興味・引き込まれる感覚"},
}

# 感情波形パターン例
WAVE_PATTERNS = """
【感情波形パターン例】
・ジェットコースター型：高→低→高→低→最高（エンタメ向き）
・螺旋型：低から少しずつ高まり転で一気に頂点（文学向き）
・断崖型：高原が続き転で急落→じわじわ回復（悲劇向き）
・波打ち型：細かい高低が続く→転で大きな波（サスペンス向き）
・静水型：静かな流れが転で大きく揺れる→余韻に消える（純文学向き）
"""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s8":  base / "s08_emotion"     / f"s08_emotion_latest_{novel_type}.md",
        "s19": base / "s19_act_structure" / f"s19_act_latest_{novel_type}.md",
        "s21": base / "s21_margin"      / f"s21_margin_latest_{novel_type}.md",
    }
    limits = {"s8": 1500, "s19": 1500, "s21": 1500}

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

    emotions_table = "\n".join(
        f"・{k}（{v['label']}）：{v['desc']} 強度範囲:{v['intensity_range'][0]}〜{v['intensity_range'][1]}"
        for k, v in SCENE_EMOTIONS.items()
    )

    return f"""あなたはこの小説作品の「感情波形設計者」です。
S8（全体感情設計）を受け取り、各章・シーンの感情波形を詳細設計してください。

{WAVE_PATTERNS}

重要思想：
・感情は「状態」ではなく「変化」として設計する
・同じ感情が続くと読者は慣れる → 必ず変化を入れる
・「緩和」がないと「緊張」が機能しない
・感情の速度（急変 / 緩やか）も設計する
・余白（S21）のある場面は感情強度を下げて余韻を作る

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【感情タイプ一覧】
{emotions_table}

【S8 全体感情設計（感情波形・読後感）】
{prev["s8"]}

【S19 起承転結設計（各章の役割・感情強度）】
{prev["s19"]}

【S21 余白設計（余白のある場面・S22引き渡しパラメータ含む）】
{prev.get("s21_table") or prev["s21"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# シーン別感情設計書（S22）

---

## ■ 感情波形パターンの選択

**この作品の感情波形パターン：**
（ジェットコースター / 螺旋 / 断崖 / 波打ち / 静水 / またはオリジナル）

**選択理由：**（S8の読後感・コンテストとの相性）

---

## ■ 章別感情波形テーブル

| 章 | 開始感情 | ピーク感情 | 終了感情 | 最大強度 | 波形の形 |
|---|--------|---------|--------|:------:|-------|
| プロローグ | | | | /10 | |
| 第1章 | | | | /10 | |
| 第2〜3章 | | | | /10 | |
| 第4〜5章 | | | | /10 | |
| ミッドポイント | | | | /10 | |
| 第6〜7章 | | | | /10 | |
| 転 | | | | /10 | |
| 第9〜10章 | | | | /10 | |
| エピローグ | | | | /10 | |

---

## ■ 感情の「高低差」設計

**最高点（強度10に近い）の場面：**
・位置（%）：
・感情タイプ：
・何がこの感情を引き起こすか：
・直前の感情（落差を作る）：

**最低点（強度1〜3）の場面：**
・位置（%）：
・感情タイプ：
・この「静けさ」が何のために必要か：
・直後の感情（ここから高まる）：

**最大の「急変」ポイント：**
（感情が最も急激に変化する瞬間）
・位置（%）：
・変化の内容：（例：安心→絶望）
・変化の速度：（急激 / 徐々に）

---

## ■ 転（75%）前後の感情設計【最重要】

**転直前（70〜74%）の感情状態：**
（どんでん返しの衝撃を最大化するための「直前の感情」）

**転の瞬間（75%）の感情：**
（反転・喪失・絶望のどれか・またはその複合）
**強度：** /10

**転直後（76〜80%）の感情：**
（どん底への落下速度）

**転→結での感情の回復曲線：**
（どの感情・タイミングで読者に「希望」を感じさせるか）

---

## ■ 余白との感情連動

S21で設計した余白（語らない・真偽不明等）と感情の接続：

S21で設計した全余白（U-1〜I-1）の行を含めること。

| 余白ID | 余白の種類 | 直前の感情強度 | 余白後の感情強度 | 余白が生む感情効果 |
|------|---------|:-----------:|:----------:|---------------|
| U-1 | 語らない | /10 | /10 | |
| U-2 | 語らない | /10 | /10 | |
| U-3 | 語らない | /10 | /10 | |
| UC-1 | 回収しない | /10 | /10 | |
| A-1 | 真偽不明 | /10 | /10 | |
| I-1 | 解釈余地 | /10 | /10 | |

**余白を「感情の間」として使う方法：**

---

## ■ 感情の「飽き」防止設計

同じ感情が続きすぎないための設計：

**最長で同じ感情が続く章（要注意）：**
**緩和を入れるタイミング：**
**「感情のリセット」シーンの設計：**
（強い感情の後に「静けさ」を入れる場所）

---

## ■ S23（シーン別プロット設計）への引き渡しパラメータ

**各シーンに感情設計を落とし込む際のルール：**
  ①
  ②
  ③

**最も重要な感情遷移（S23で最優先で設計するシーン）：**
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

    print("\n[S22] シーン別感情設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  感情タイプ: {len(SCENE_EMOTIONS)}種")

    prev = load_prev_outputs(novel_type)

    # fix①: S21のS22引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s21_path = _Path(__file__).parent.parent / "output" / "s21_margin" \
               / f"s21_margin_latest_{novel_type}.md"
    if _s21_path.exists():
        _s21_full = _s21_path.read_text(encoding="utf-8")
        _idx = _s21_full.rfind("## ■ S22（シーン別感情設計）への引き渡しパラメータ")
        prev["s21_table"] = _s21_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s21_table"] = ""

    prompt = build_prompt(prev, novel_type)
    print("  感情波形設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# シーン別感情設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s22_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s22_emotion_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_シーン別感情設計")},
            "スキル":     {"rich_text": txt("S22_感情波形設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "シーン別感情設計", result)

    print("[S22] 完了\n")
    print("  次のステップ: S23（シーン別プロット設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 23 --type {novel_type}")

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
