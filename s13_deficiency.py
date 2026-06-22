# -*- coding: utf-8 -*-
"""
S13：キャラ欠落分析スキル
呼び出し：python run_pipeline.py --skill 13 --type short
役割：S10〜S12の全キャラ設計を統合し、主人公を
     「テーマの欠落体現者」として確定する。
     欠落とは「できない・持てない・見えない」という現在の不完全性。

重要思想：
  欠落の例：
    テーマ「愛」     → 主人公は「愛せない」
    テーマ「自由」   → 主人公は「選べない」
    テーマ「命」     → 主人公は「死ねない（または生きられない）」
    テーマ「信頼」   → 主人公は「信じられない」

  欠落 ≠ 弱点：
    弱点は「頑張れば克服できるもの」
    欠落は「そもそも持っていないもの」→ 物語を通じて初めて獲得される

次ステップ：S14（全体プロット設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s13_deficiency"


# ============================================================
# 欠落タイプ定義
# ============================================================

DEFICIENCY_TYPES = {
    "cannot_love":    "愛せない（愛したいが、愛することが何かわからない/怖い）",
    "cannot_choose":  "選べない（自由を持てない/選択の重みに耐えられない）",
    "cannot_trust":   "信じられない（信頼したいが、裏切りが怖い）",
    "cannot_feel":    "感じられない（感情が死んでいる/麻痺している）",
    "cannot_stay":    "留まれない（どこにも居場所を持てない）",
    "cannot_ask":     "求められない（助けを求めることができない）",
    "cannot_forgive": "赦せない（自分を・他者を赦す方法を知らない）",
    "cannot_exist":   "存在できない（自分が存在していい理由がわからない）",
    "cannot_lose":    "失えない（手放すことができない・何かに縛られている）",
    "cannot_hope":    "希望を持てない（未来を信じられない）",
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s7":  base / "s07_philosophy"  / f"s07_philosophy_latest_{novel_type}.md",
        "s9":  base / "s09_theme"       / f"s09_theme_latest_{novel_type}.md",
        "s10": base / "s10_character"   / f"s10_character_latest_{novel_type}.md",
        "s11": base / "s11_personality" / f"s11_personality_latest_{novel_type}.md",
        "s12": base / "s12_trauma"      / f"s12_trauma_latest_{novel_type}.md",
    }
    limits = {"s7": 1500, "s9": 1500, "s10": 1500, "s11": 1500, "s12": 1500}

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

    deficiency_list = "\n".join(
        f"・{k}：{v}" for k, v in DEFICIENCY_TYPES.items()
    )

    return f"""あなたはこの小説作品の「欠落分析者」です。
S10〜S12の全キャラ設計を統合し、
主人公を「テーマの欠落体現者」として確定してください。

【欠落とは何か】
・欠落 ≠ 弱点：弱点は努力で克服できる。欠落は「そもそも持っていないもの」
・欠落は物語開始時点では「本人も気づいていない」ことが理想
・欠落は物語を通じて初めて「気づき」→「獲得の試み」→「部分的な獲得」となる
・完全に獲得できなくてもいい。気づくだけで十分なこともある

【欠落タイプ参考一覧】
{deficiency_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S9テーマ（大テーマ・欠落接続）】
{prev["s9"]}

【S7哲学的問い】
{prev["s7"]}

【S12トラウマ設計（S13引き渡しテーブル含む）】
{prev.get("s12_table") or prev["s12"]}

【S11性格設計（矛盾の核）】
{prev["s11"]}

【S10キャラクター設計（問いへの立場）】
{prev["s10"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

# キャラ欠落分析書（S13）

---

## ■ 主人公の欠落確定

**欠落タイプ：**（上記リストから選択または独自設計）

**欠落の定義（この作品固有）：**
（「〜できない」または「〜を持てない」という形で1文）

**欠落とテーマの接続：**
（大テーマの「どの側面を体現できていないか」）

**欠落とトラウマの接続：**
（この欠落がS12のトラウマからどう生まれているか）

**欠落と矛盾の接続：**
（S11の矛盾①②③のどれが欠落から生まれているか）

**本人が欠落に気づいていない理由：**
（なぜ自分でも気づけないのか）

---

## ■ 欠落の物語内での機能

**欠落が「見える」最初の場面（序盤）：**
（読者には見えるが主人公は気づいていない場面）

**欠落が「痛み」になる場面（中盤）：**
（欠落が原因で誰かを傷つける・機会を逃す瞬間）

**欠落に「初めて気づく」場面（転）：**
（どんでん返しと連動した気づきの瞬間）

**欠落の「獲得の試み」（結）：**
（完全には獲得できないとしても、何を試みるか）

**読後感との接続：**
（欠落の部分的な獲得がS8の読後感をどう生み出すか）

---

## ■ 相方の欠落設計

**欠落タイプ：**
**欠落の定義：**
**主人公の欠落との「補完関係」または「衝突関係」：**
（2つの欠落が組み合わさることで生まれるドラマ）
**相方の欠落が主人公の欠落を「映す鏡」になる方法：**

---

## ■ 対立者の欠落設計

**欠落タイプ：**
**欠落の定義：**
**対立者の欠落が「問いの別の答え」を体現する方法：**
（対立者は欠落を「別の形で解決した」存在として設計）
**対立者の解決法がなぜ「間違い」ではなく「別の答え」に見えるか：**

---

## ■ キャラクター欠落マップ

S10で設計した全キャラクターの行を含めること。

| キャラ | 欠落タイプ | 欠落の定義 | テーマとの接続 | 獲得の可能性 |
|------|---------|---------|-----------|----------|
| 主人公（碧） | | | | 部分的 / 気づきのみ / 未獲得 |
| 相方（柚） | | | | |
| 対立者（本敵B：久我） | | | | |
| 対立者（偽敵A：三島） | | | | |
| サブキャラ①（中根） | | | | |
| 相方の友人（静） | | | | |

---

## ■ 欠落が「問い」を動かす仕組み

**核心の問いと主人公の欠落の関係：**
（問いを生きられないことが欠落の本質）

**欠落があることで問いが「答えられない」理由：**
（欠落が問いへの回答を阻む構造）

**欠落が部分的に満たされたとき問いはどう変化するか：**

---

## ■ S14（全体プロット設計）への引き渡しパラメータ

**プロット設計で守るべき欠落の制約：**
（欠落が「都合よく解決されない」ための具体的なルール）
  ①
  ②
  ③

**欠落が最も機能する3つのシーン（プロット配置推奨）：**
  場面①（序盤）：
  場面②（中盤）：
  場面③（クライマックス）：

**キャラクター設計完了サマリー（S10〜S13の統合）：**
（主人公・相方・本敵B・偽敵A・サブキャラ①・相方の友人の設計を3〜4行で要約）
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

    print("\n[S13] キャラ欠落分析スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    # fix①: S12のS13引き渡しテーブルはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s12_path = _Path(__file__).parent.parent / "output" / "s12_trauma" \
               / f"s12_trauma_latest_{novel_type}.md"
    if _s12_path.exists():
        _s12_full = _s12_path.read_text(encoding="utf-8")
        _idx = _s12_full.rfind("## ■ S13（キャラ欠落分析）への引き渡しパラメータ")
        prev["s12_table"] = _s12_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s12_table"] = ""

    prompt = build_prompt(prev)
    print("  欠落分析中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# キャラ欠落分析
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s13_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s13_deficiency_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_欠落分析")},
            "スキル":     {"rich_text": txt("S13_欠落分析")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "キャラ欠落分析", result)

    print("[S13] 完了\n")
    print("  ✅ キャラクター設計フェーズ（S10〜S13）完了")
    print("  次のステップ: S14（全体プロット設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 14 --type {novel_type}")

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
