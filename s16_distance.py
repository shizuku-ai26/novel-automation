# -*- coding: utf-8 -*-
"""
S16：主線と並行線の距離感設計スキル
呼び出し：python run_pipeline.py --skill 16 --type short
役割：S15で設計した並行線それぞれの「距離感」を精密に設計する。
     ・どれくらい独立するか
     ・どれくらい交差するか
     ・どれくらいテーマが共鳴するか

重要思想：
  近すぎる並行線 → メインプロットの重複になる
  遠すぎる並行線 → テーマの散漫化・読者が迷子になる
  最適な距離感   → 「独立しているが磁力で引き合う」

次ステップ：S17（共鳴点設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s16_distance"


# ============================================================
# 距離感パラメータ定義
# ============================================================

DISTANCE_AXES = {
    "independence": {
        "label": "独立度",
        "desc":  "並行線がメインプロットなしでも成立するか",
        "low":   "1：完全従属（メインなしでは意味をなさない）",
        "mid":   "3：半独立（メインと連動しつつ独自の物語も持つ）",
        "high":  "5：完全独立（それだけで一つの短編になる）",
        "optimal": "2〜4が理想。1は補完エピソード、5は別作品になる",
    },
    "intersection": {
        "label": "交差頻度",
        "desc":  "どのくらいの頻度でメインプロットと交差するか",
        "low":   "1：ほぼ交差しない（転のみ）",
        "mid":   "3：要所で交差（承前半・ミッド・転・結）",
        "high":  "5：常に交差（ほぼ並走）",
        "optimal": "2〜4が理想。頻度が高いほどテンポが落ちる",
    },
    "resonance": {
        "label": "テーマ共鳴度",
        "desc":  "並行線がメインプロットのテーマとどれくらい共鳴するか",
        "low":   "1：テーマと無関係（完全な対比・別世界）",
        "mid":   "3：テーマの別側面（間接的に照射）",
        "high":  "5：テーマの直接体現（ほぼ同じ問いを問う）",
        "optimal": "2〜4が理想。5は重複感が出る",
    },
}

# 距離感の黄金比
GOLDEN_RATIOS = {
    "相方キャラ": {
        "independence": 3, "intersection": 4, "resonance": 4,
        "comment": "近いが重複しない。感情的に主線と深く絡む",
    },
    "サブキャラ":  {
        "independence": 4, "intersection": 2, "resonance": 3,
        "comment": "独立性が高く、要所で主線を揺さぶる",
    },
    "対立者":      {
        "independence": 3, "intersection": 3, "resonance": 5,
        "comment": "テーマの反転鏡。転で完全に交差する",
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
        "s14": base / "s14_plot_main"  / f"s14_plot_latest_{novel_type}.md",
        "s15": base / "s15_subplot"    / f"s15_subplot_latest_{novel_type}.md",
    }
    limits = {"s7": 1500, "s14": 1500, "s15": 1500}

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

    axes_text = "\n".join(
        f"【{v['label']}（{k}）】\n"
        f"  定義：{v['desc']}\n"
        f"  低(1)：{v['low']}\n"
        f"  中(3)：{v['mid']}\n"
        f"  高(5)：{v['high']}\n"
        f"  最適範囲：{v['optimal']}"
        for k, v in DISTANCE_AXES.items()
    )

    golden_text = "\n".join(
        f"・{role}：独立度{v['independence']} / 交差{v['intersection']} / 共鳴{v['resonance']} → {v['comment']}"
        for role, v in GOLDEN_RATIOS.items()
    )

    return f"""あなたはこの小説作品の「距離感設計者」です。
S15で設計した各並行線の「距離感」を精密に設計してください。

重要思想：
・近すぎる並行線 → メインプロットの重複・読者が混乱
・遠すぎる並行線 → テーマの散漫化・読者が迷子
・最適な距離感   → 「独立しているが磁力で引き合う」関係

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【3軸の定義】
{axes_text}

【黄金比（参考）】
{golden_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S15 並行線設計（引き渡しパラメータ含む）】
{prev.get("s15_table") or prev["s15"]}

【S14 全体プロット設計（メイン構造）】
{prev["s14"]}

【S7 哲学的問い（テーマ共鳴の基準）】
{prev["s7"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 距離感設計書（S16）

---

## ■ 距離感パラメータ確定

| 並行線 | 独立度(1-5) | 交差頻度(1-5) | テーマ共鳴度(1-5) | 総評 |
|------|:---------:|:----------:|:------------:|-----|
| 相方キャラ | | | | |
| サブキャラ | | | | |
| 対立者 | | | | |

**黄金比との差異がある場合の理由：**

---

## ■ 相方キャラの距離感詳細設計

**独立度（確定値）：**
**このパラメータが意味すること（この作品固有）：**
（相方の並行線がメインなしでどこまで成立するか）

**交差頻度（確定値）：**
**交差タイミングの設計：**
| 交差点 | 位置（%） | 交差の内容 | メイン主人公への影響 |
|------|:--------:|---------|--------------|
| 第1交差 | | | |
| 第2交差 | | | |
| 第3交差（転） | | | |

**テーマ共鳴度（確定値）：**
**相方の並行線が照射するテーマの側面：**
**メインプロットとの「ずれ」がドラマになる部分：**
（同じテーマを違う角度で問うことで生まれる緊張感）

---

## ■ サブキャラの距離感詳細設計

**独立度・交差頻度・テーマ共鳴度（確定値）：**
**サブキャラの並行線がメインプロットに「驚き」を与えるタイミング：**
**「遠い」からこそ生まれる効果：**
（メインプロットと距離があることで可能になる描写）

---

## ■ 対立者の距離感詳細設計

**独立度・交差頻度・テーマ共鳴度（確定値）：**
**転（75%）での完全交差の設計：**
（どんでん返しと対立者の並行線がどう交差するか）
**テーマ共鳴度が高い理由：**
（対立者がテーマの「反転鏡」として機能する仕組み）

---

## ■ 3本の並行線の「磁力関係」

並行線同士がどう引き合い・反発するかを設計：

**相方×サブキャラの磁力：**
（引き合う / 反発する / 交差しない）

**相方×対立者の磁力：**

**サブキャラ×対立者の磁力：**

**3本全てが交差する瞬間（もしあれば）：**
（最大のドラマが生まれる「集結点」）

---

## ■ 距離感の「揺れ」設計

物語を通じて距離感が変化する設計：

| 時期 | 相方距離 | サブ距離 | 対立者距離 | 変化の理由 |
|-----|:------:|:------:|:-------:|---------|
| 序盤（0-25%） | | | | |
| 中盤（25-75%） | | | | |
| 転後（75-100%） | | | | |

**最も距離が縮まる瞬間：**
**最も距離が離れる瞬間：**

---

## ■ S17（共鳴点設計）への引き渡しパラメータ

**最重要の共鳴点（並行線がメインプロットを最も強く照射する瞬間）：**
  相方：
  サブキャラ：
  対立者：

**共鳴の形（S17で設計する3パターンの方向性）：**
・サブが主線を否定する可能性：
・サブが主線を先読みする可能性：
・サブが主線の未来になる可能性：
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

    print("\n[S16] 距離感設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    # fix①: S15のS16引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s15_path = _Path(__file__).parent.parent / "output" / "s15_subplot" \
               / f"s15_subplot_latest_{novel_type}.md"
    if _s15_path.exists():
        _s15_full = _s15_path.read_text(encoding="utf-8")
        _idx = _s15_full.rfind("## ■ S16（距離感設計）への引き渡しパラメータ")
        prev["s15_table"] = _s15_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s15_table"] = ""

    prompt = build_prompt(prev)
    print("  距離感設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 主線と並行線の距離感設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s16_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s16_distance_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_距離感設計")},
            "スキル":     {"rich_text": txt("S16_距離感設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "距離感設計", result)

    print("[S16] 完了\n")
    print("  次のステップ: S17（共鳴点設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 17 --type {novel_type}")

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
