# -*- coding: utf-8 -*-
"""
S18：伏線設計スキル
呼び出し：python run_pipeline.py --skill 18 --type short
役割：5種類の伏線を分離管理し、配置・回収を設計する。
     最重要は「感情伏線」。情報伏線に偏るとミステリになる。

5種類：
  情報伏線  ：事実・データ・出来事として提示される伏線
  感情伏線  ：感情・関係性の変化として提示される伏線（最重要）
  台詞伏線  ：セリフとして提示される伏線
  モチーフ伏線：象徴・物・場所・色として提示される伏線
  構図伏線  ：場面の構図・視点・カメラワークとして提示される伏線

次ステップ：S19（起承転結設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s18_foreshadow"


# ============================================================
# 伏線5種類定義
# ============================================================

FORESHADOW_TYPES = {
    "emotion": {
        "label":    "感情伏線",
        "priority": "★★★最重要",
        "desc":     "感情・関係性の変化として提示される伏線",
        "example":  "主人公が相方に対して「なぜか安心する」感覚→転後に「守られていた」と判明",
        "strength": "読者が論理より先に感じ取る。どんでん返し後の「ああ、あれはそういうことだったのか」が最も深い",
        "trap":     "感情伏線だけだと「何かありそう」感が強すぎて読者がバレる",
    },
    "information": {
        "label":    "情報伏線",
        "priority": "★★重要",
        "desc":     "事実・データ・出来事として提示される伏線",
        "example":  "第1章で「鍵は3つある」→転後に「3つ目の鍵が主人公の手にあった」と判明",
        "strength": "論理的な整合性を担保する。「ちゃんと証拠があった」という納得感",
        "trap":     "情報伏線が多すぎるとミステリになり、テーマが埋もれる",
    },
    "dialogue": {
        "label":    "台詞伏線",
        "priority": "★★重要",
        "desc":     "セリフとして提示される伏線",
        "example":  "「君は必ず帰ってくる」→転後に「戻れない状況を知った上での言葉」と判明",
        "strength": "読者に強く印象づけられる。回収時の「あの言葉は！」という衝撃が大きい",
        "trap":     "台詞伏線が多すぎると「全ての台詞が意味深」になり不自然",
    },
    "motif": {
        "label":    "モチーフ伏線",
        "priority": "★普通",
        "desc":     "象徴・物・場所・色として提示される伏線",
        "example":  "主人公が常に握っている石→転後に「亡くなった誰かが最後に渡したもの」と判明",
        "strength": "読者の無意識に働きかける。気づかなくても感じさせる",
        "trap":     "モチーフが多すぎると「何の意味があるの？」と読者が疲弊する",
    },
    "composition": {
        "label":    "構図伏線",
        "priority": "★普通",
        "desc":     "場面の構図・視点・カメラワークとして提示される伏線",
        "example":  "常に主人公の「後ろ」にいる人物→転後に「ずっと守っていた」と判明",
        "strength": "映像的な記憶として残る。視覚的に「あの場面！」と蘇る",
        "trap":     "文章では伝わりにくい。過度に使うと説明的になる",
    },
}

# 推奨配分（短編）
RECOMMENDED_COUNT = {
    "short":  {"emotion": 3, "information": 2, "dialogue": 2, "motif": 2, "composition": 1},
    "medium": {"emotion": 4, "information": 3, "dialogue": 3, "motif": 3, "composition": 2},
    "long":   {"emotion": 5, "information": 4, "dialogue": 4, "motif": 4, "composition": 3},
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s1":  base / "s01_plot_twist"  / f"s01_twist_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"  / f"s07_philosophy_latest_{novel_type}.md",
        "s14": base / "s14_plot_main"   / f"s14_plot_latest_{novel_type}.md",
        "s17": base / "s17_resonance"   / f"s17_resonance_latest_{novel_type}.md",
    }
    limits = {"s1": 1500, "s7": 1500, "s14": 1500, "s17": 1500}

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

    types_text = "\n".join(
        f"【{v['label']}（{k}）{v['priority']}】\n"
        f"  概要：{v['desc']}\n"
        f"  例：{v['example']}\n"
        f"  強み：{v['strength']}\n"
        f"  罠：{v['trap']}"
        for k, v in FORESHADOW_TYPES.items()
    )

    counts = RECOMMENDED_COUNT.get(novel_type, RECOMMENDED_COUNT["short"])
    count_text = " / ".join(
        f"{FORESHADOW_TYPES[k]['label']}:{v}本"
        for k, v in counts.items()
    )

    return f"""あなたはこの小説作品の「伏線設計者」です。
5種類の伏線を分離管理し、配置・回収を設計してください。

重要思想：
・最重要は「感情伏線」。論理より先に読者の心に刺さる
・情報伏線に偏るとミステリになりテーマが埋もれる
・「自然に配置・必然的に回収」が原則
・読者が「え、これ伏線だったの？」と言える設計を目指す

【推奨本数（{novel_type}）】
{count_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【5種類の定義】
{types_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S1 どんでん返し設計（最終回収点）】
{prev["s1"]}

【S14 全体プロット設計（配置・回収のタイムライン）】
{prev["s14"]}

【S17 共鳴点設計（伏線の種・引き渡しパラメータ）】
{prev.get("s17_table") or prev["s17"]}

【S7 哲学的問い（伏線のテーマとの接続）】
{prev["s7"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で設計してください：

---

# 伏線設計書（S18）

---

## ■ 伏線一覧テーブル

| ID | 種別 | 配置位置（%） | 回収位置（%） | 内容（提示時） | 回収時の意味 |
|----|------|:----------:|:----------:|------------|----------|
| E-1 | 感情 | | | | |
| E-2 | 感情 | | | | |
| E-3 | 感情 | | | | |
| I-1 | 情報 | | | | |
| I-2 | 情報 | | | | |
| D-1 | 台詞 | | | | |
| D-2 | 台詞 | | | | |
| M-1 | モチーフ | | | | |
| M-2 | モチーフ | | | | |
| C-1 | 構図 | | | | |

---

## ■ 感情伏線の詳細設計（最重要）

### E-1
**配置位置：**（%・幕）
**提示の形：**（読者にはどんな感情・関係の変化として見えるか）
**配置時の「自然な見え方」：**（伏線と気づかれない理由）
**回収位置：**（%・転 or 結）
**回収時の意味：**（どんでん返し後に何が明らかになるか）
**「ああ、あれはそういうことだったのか」の内容：**
**テーマとの接続：**

### E-2
**配置・提示・回収（E-1と同形式）：**

### E-3
**配置・提示・回収（E-1と同形式）：**

---

## ■ 情報伏線の詳細設計

### I-1
**配置位置：** / **提示の形：** / **回収位置：** / **回収時の意味：**
**論理的整合性の確認：**（この伏線が「フェア」である理由）

### I-2
**配置・提示・回収：**

---

## ■ 台詞伏線の詳細設計

### D-1
**配置位置：**
**台詞の内容（具体的に）：**
**配置時の「表の意味」：**（この台詞が最初に持つ意味）
**回収時の「裏の意味」：**（どんでん返し後に明かされる本当の意味）

### D-2
**台詞・表の意味・裏の意味：**

---

## ■ モチーフ伏線の詳細設計

### M-1
**モチーフ（物・場所・色など）：**
**最初の登場シーン：**
**繰り返し登場するパターン：**（何回・どのタイミングで）
**転後の「意味の書き換え」：**

### M-2
**モチーフ・登場・書き換え：**

---

## ■ 構図伏線の詳細設計

### C-1
**構図の内容：**（誰が・どこに・どう配置されているか）
**初登場シーン：**
**同じ構図が繰り返されるタイミング：**
**転後に構図が「逆転」または「完成」する瞬間：**

---

## ■ 伏線の配置タイムライン

| 位置（%） | ID | 種別 | 配置内容（1文） |
|:--------:|----|------|------------|
| 0〜15% | | | |
| 15〜49% | | | |
| 50% | | | |
| 50〜74% | | | |
| 75% | | | |
| 75〜100% | | | |

---

## ■ どんでん返しとの接続確認

**転（75%）で一気に回収される伏線リスト：**
（複数の伏線が同時に回収されることで衝撃が最大化する）

**「フェア」の確認：**
（全ての伏線が、転より前に提示されているか）

**「アンフェア」な伏線がないかの確認：**
（後から都合よく追加された感がある伏線はないか）

---

## ■ S19（起承転結設計）への引き渡しパラメータ

**各幕に配置すべき伏線の優先順：**
  プロローグ：
  起：
  承前半：
  ミッドポイント：
  承後半：
  転：（回収）
  結：（最終回収）
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

    print("\n[S18] 伏線設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    rec = RECOMMENDED_COUNT.get(novel_type, RECOMMENDED_COUNT["short"])
    total = sum(rec.values())
    print(f"  推奨伏線数: 合計{total}本（感情{rec['emotion']}・情報{rec['information']}・台詞{rec['dialogue']}・モチーフ{rec['motif']}・構図{rec['composition']}）")

    prev = load_prev_outputs(novel_type)

    # fix①: S17のS18引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s17_path = _Path(__file__).parent.parent / "output" / "s17_resonance" \
               / f"s17_resonance_latest_{novel_type}.md"
    if _s17_path.exists():
        _s17_full = _s17_path.read_text(encoding="utf-8")
        _idx = _s17_full.rfind("## ■ S18（伏線設計）への引き渡しパラメータ")
        prev["s17_table"] = _s17_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s17_table"] = ""

    prompt = build_prompt(prev, novel_type)
    print("  伏線設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# 伏線設計
実行日時：{timestamp}
小説タイプ：{novel_type}
推奨伏線数：合計{total}本

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s18_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s18_foreshadow_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_伏線設計")},
            "スキル":     {"rich_text": txt("S18_伏線設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "伏線設計", result)

    print("[S18] 完了\n")
    print("  次のステップ: S19（起承転結設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 19 --type {novel_type}")

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
