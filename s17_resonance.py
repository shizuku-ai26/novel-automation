# -*- coding: utf-8 -*-
"""
S17：共鳴点設計スキル
呼び出し：python run_pipeline.py --skill 17 --type short
役割：並行線がメインプロットと「共鳴する瞬間」を精密に設計する。
     共鳴の3パターン：
       ・サブが主線を否定する（主人公の答えを揺さぶる）
       ・サブが主線を先読みする（主人公より先に答えに到達する）
       ・サブが主線の未来になる（主人公の先にある姿を体現する）

重要思想：
  共鳴点は「並行線とメインプロットが磁力で引き合う瞬間」
  この瞬間にテーマが最も深く・自然に伝わる

次ステップ：S18（伏線設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s17_resonance"


# ============================================================
# 共鳴パターン定義
# ============================================================

RESONANCE_PATTERNS = {
    "denial": {
        "label":   "否定型",
        "desc":    "サブが主線を否定する。主人公の答えを揺さぶる。",
        "example": "主人公が「愛は守ること」と信じているとき、サブが「愛は手放すこと」を体現する",
        "effect":  "主人公の答えが揺らぎ、どんでん返しへの準備が深まる",
        "timing":  "承後半（60〜74%）が最も効果的。転直前の最後の揺さぶり",
    },
    "foreshadow": {
        "label":   "先読み型",
        "desc":    "サブが主線を先読みする。主人公より先に答えに到達する。",
        "example": "相方がすでに「欠落を受け入れた」状態で、主人公はまだそこに辿り着けていない",
        "effect":  "読者は先を知りながら主人公を見守る緊張感が生まれる",
        "timing":  "ミッドポイント〜承後半に配置すると転の衝撃が増す",
    },
    "future": {
        "label":   "未来型",
        "desc":    "サブが主線の未来になる。主人公の先にある姿を体現する。",
        "example": "サブキャラが「欠落を抱えたまま生きることを選んだ存在」として機能する",
        "effect":  "主人公の結末への「予告」として機能。希望または警告になる",
        "timing":  "序盤〜中盤に配置し、終盤で「そういうことだったのか」と回収",
    },
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s7":  base / "s07_philosophy" / f"s07_philosophy_latest_{novel_type}.md",
        "s13": base / "s13_deficiency" / f"s13_deficiency_latest_{novel_type}.md",
        "s14": base / "s14_plot_main"  / f"s14_plot_latest_{novel_type}.md",
        "s15": base / "s15_subplot"    / f"s15_subplot_latest_{novel_type}.md",
        "s16": base / "s16_distance"   / f"s16_distance_latest_{novel_type}.md",
    }
    limits = {"s7": 1500, "s13": 1500, "s14": 1500, "s15": 1500, "s16": 1500}

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

def build_prompt(prev: dict) -> str:

    patterns_text = "\n".join(
        f"【{v['label']}（{k}）】\n"
        f"  概要：{v['desc']}\n"
        f"  例：{v['example']}\n"
        f"  効果：{v['effect']}\n"
        f"  最適タイミング：{v['timing']}"
        for k, v in RESONANCE_PATTERNS.items()
    )

    return f"""あなたはこの小説作品の「共鳴点設計者」です。
各並行線がメインプロットと「共鳴する瞬間」を精密に設計してください。

重要思想：
・共鳴点は「テーマが説明なしに最も深く伝わる瞬間」
・直接的な説明は不要。場面と行動が共鳴することで読者が感じ取る
・共鳴が多すぎると「くどい」・少なすぎると「伝わらない」

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【共鳴の3パターン】
{patterns_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S16 距離感設計（共鳴の引き渡しパラメータ含む）】
{prev.get("s16_table") or prev["s16"]}

【S15 並行線設計】
{prev["s15"]}

【S14 全体プロット設計（転・各幕の構造）】
{prev["s14"]}

【S13 欠落分析（主人公の欠落・問いへの答え）】
{prev["s13"]}

【S7 哲学的問い（共鳴の基準）】
{prev["s7"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 共鳴点設計書（S17）

---

## ■ 共鳴点マップ（全体）

| 並行線 | 共鳴パターン | 位置（%） | 共鳴の内容（1文） |
|------|-----------|:--------:|--------------|
| 相方キャラ | 否定/先読み/未来 | | |
| 相方キャラ | 否定/先読み/未来 | | |
| サブキャラ | 否定/先読み/未来 | | |
| 対立者 | 否定/先読み/未来 | | |
| 対立者 | 否定/先読み/未来 | | |

---

## ■ 相方キャラの共鳴点設計

**共鳴パターン①：**（否定 / 先読み / 未来）

**位置：**（物語の何%地点）

**共鳴の場面：**
（具体的にどのシーン・行動・台詞で共鳴が起きるか）

**主人公のその時点での「問いへの答え」：**

**相方の行動・状態が示す「別の答え」：**

**読者が感じること：**
（この共鳴で読者の心にどんな問いが生まれるか）

**テーマが「滲み出る」方法：**
（説明せずにどう伝わるか）

---

**共鳴パターン②（任意）：**

**位置：** / **共鳴の場面：** / **効果：**

---

## ■ サブキャラの共鳴点設計

**共鳴パターン：**（否定 / 先読み / 未来）
**位置：**
**共鳴の場面：**
**サブキャラが「未来の主人公像」として機能する場合：**
（主人公がこの先どうなるかの「予告」として）
**テーマが「滲み出る」方法：**

---

## ■ 対立者の共鳴点設計

**共鳴パターン①：**（否定 / 先読み / 未来）
**位置：**
**共鳴の場面：**

**対立者が「テーマの反転答え」を体現する方法：**
（主人公が「できない」ことを、対立者は「別の形でできてしまっている」）

**転（75%）での最大共鳴：**
（どんでん返しと対立者の共鳴が交差する瞬間）
**この交差でどんでん返しがどう増幅されるか：**

---

## ■ 共鳴の「密度」設計

共鳴が多すぎず少なすぎない配置を設計：

**序盤（0〜25%）の共鳴数：**（推奨：1〜2個）
**中盤（25〜75%）の共鳴数：**（推奨：3〜4個）
**終盤（75〜100%）の共鳴数：**（推奨：2〜3個）

**最も重要な共鳴点TOP3（優先順）：**
  1位：
  2位：
  3位：

---

## ■ 「語らない」共鳴の設計

共鳴点でテーマを「語らせない」ための具体的なルール：

**禁止事項（3つ）：**
（この作品で「共鳴の瞬間」に登場人物に語らせてはいけないこと）
  ①
  ②
  ③

**代わりに使う表現手法：**
（身体描写・沈黙・天候・モチーフなど、語らずに伝える方法）

---

## ■ S18（伏線設計）への引き渡しパラメータ

**共鳴点に埋め込むべき伏線の種（3つ）：**
（共鳴の瞬間に自然に仕込める伏線候補）
  ①
  ②
  ③

**転（75%）の共鳴が最大化するために必要な伏線：**
（転でのどんでん返しと並行線の交差を必然にするための伏線）

**S18で設計すべき伏線の種別（感情/情報/台詞/モチーフ/構図）の優先順：**
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

    print("\n[S17] 共鳴点設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    # fix②: S16のS17引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s16_path = _Path(__file__).parent.parent / "output" / "s16_distance" \
               / f"s16_distance_latest_{novel_type}.md"
    if _s16_path.exists():
        _s16_full = _s16_path.read_text(encoding="utf-8")
        _idx = _s16_full.rfind("## ■ S17（共鳴点設計）への引き渡しパラメータ")
        prev["s16_table"] = _s16_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s16_table"] = ""

    prompt = build_prompt(prev)
    print("  共鳴点設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 共鳴点設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s17_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s17_resonance_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_共鳴点設計")},
            "スキル":     {"rich_text": txt("S17_共鳴点設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "共鳴点設計", result)

    print("[S17] 完了\n")
    print("  次のステップ: S18（伏線設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 18 --type {novel_type}")

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
