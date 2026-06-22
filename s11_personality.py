# -*- coding: utf-8 -*-
"""
S11：X軸Y軸性格設計スキル
呼び出し：python run_pipeline.py --skill 11 --type short
役割：S10の「矛盾の核」を受け取り、各キャラクターの性格を
     MBTI的な分類ではなく「矛盾」として設計する。
     X軸（行動軸）× Y軸（価値軸）の2軸で性格の立体感を作る。

重要思想：
  弱い性格設計：「明るくて前向き」「クールで無口」
  強い性格設計：「優しいが支配欲が強い」「臆病なのに破滅願望がある」

次ステップ：S12（トラウマ設計）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s11_personality"


# ============================================================
# X軸（行動軸）定義
# ============================================================

X_AXIS = {
    "active":   {
        "label": "能動的",
        "desc":  "自分から動く・決断が早い・状況を変えようとする",
        "risk":  "暴走・周囲を巻き込む・後先を考えない",
    },
    "reactive": {
        "label": "受動的",
        "desc":  "状況に反応する・慎重・流れを読んでから動く",
        "risk":  "機会を逃す・他者に依存する・意思が見えない",
    },
    "mixed":    {
        "label": "状況依存（能動×受動の振れ幅が大きい）",
        "desc":  "普段は受動的だが特定の条件で能動的に爆発する",
        "risk":  "予測不能・周囲を混乱させる・自分でも制御できない",
    },
}

# ============================================================
# Y軸（価値軸）定義
# ============================================================

Y_AXIS = {
    "self":       {
        "label": "自己中心",
        "desc":  "自分の感情・欲求・生存を優先する",
        "risk":  "他者を傷つける・孤立する・共感されにくい",
        "drama": "自分を大切にすることと他者を傷つけることが衝突する",
    },
    "other":      {
        "label": "他者中心",
        "desc":  "他者の感情・安全・幸福を優先する",
        "risk":  "自己を犠牲にする・搾取される・本音を言えない",
        "drama": "他者のために生きることが自分を壊していく",
    },
    "principle":  {
        "label": "原則中心",
        "desc":  "ルール・正義・信念を個人の感情より優先する",
        "risk":  "融通が利かない・感情を切り捨てる・孤立",
        "drama": "原則を守ることと愛する人を守ることが矛盾する",
    },
    "survival":   {
        "label": "生存中心",
        "desc":  "生き延びることを最優先・感情より現実",
        "risk":  "冷酷に見える・信頼されない・孤独",
        "drama": "生き延びるために愛するものを捨てる選択が迫られる",
    },
}

# ============================================================
# 矛盾パターン例（プロンプト内で参照）
# ============================================================

CONTRADICTION_EXAMPLES = """
【強い矛盾パターン例】
✅ 「優しいが支配欲が強い」→ 愛の名の下に相手の自由を奪う
✅ 「臆病なのに破滅願望がある」→ 生存本能と自己否定が共存
✅ 「愛したいのに他人を壊す」→ 近づくほど傷つける
✅ 「正義を信じるが手段を選ばない」→ 目的と方法の矛盾
✅ 「誰かに必要とされたいが孤独を求める」→ 繋がりへの恐怖
✅ 「感情を持たないように見えるが最も感情的」→ 抑圧と爆発
✅ 「強さを誇示するが誰よりも傷つきやすい」→ 鎧と素肌
✅ 「他者を救いたいが自分を罰したい」→ 救済と自己破壊の共存

【弱い性格描写（避けるべき）】
❌ 明るくて前向き
❌ クールで無口
❌ 優しくて思いやりがある
❌ 真面目で誠実
❌ 不思議系・天然
"""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s7":  base / "s07_philosophy" / f"s07_philosophy_latest_{novel_type}.md",
        "s9":  base / "s09_theme"      / f"s09_theme_latest_{novel_type}.md",
        "s10": base / "s10_character"  / f"s10_character_latest_{novel_type}.md",
    }
    limits = {"s7": 1500, "s9": 1500, "s10": 6000}

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

    # X軸・Y軸テーブル
    x_table = "\n".join(
        f"・{k}（{v['label']}）：{v['desc']} → リスク：{v['risk']}"
        for k, v in X_AXIS.items()
    )
    y_table = "\n".join(
        f"・{k}（{v['label']}）：{v['desc']} → ドラマ：{v['drama']}"
        for k, v in Y_AXIS.items()
    )

    return f"""あなたはこの小説作品の「性格設計者」です。
S10で設計した各キャラクターの「矛盾の核」を受け取り、
X軸（行動軸）× Y軸（価値軸）で性格の立体感を設計してください。

{CONTRADICTION_EXAMPLES}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【X軸（行動軸）定義】
{x_table}

【Y軸（価値軸）定義】
{y_table}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【S10キャラクター設計（矛盾の核・引き渡しテーブル含む）】
{prev["s10"]}

【S7哲学的問い（参考）】
{prev["s7"]}

【S9テーマ設計（参考）】
{prev["s9"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

# X軸Y軸性格設計書（S11）

---

S10で設計した全キャラクター（主人公・相方・対立者・サブキャラ等、S10の人数に従う）について
以下の形式で設計してください：

---

## ■ 主人公の性格設計

**X軸（行動軸）：**（active / reactive / mixed）
**Y軸（価値軸）：**（self / other / principle / survival）

**矛盾①（表の性格 × 隠れた性格）：**
（「〜だが〜」という形で1文）

**矛盾②（行動パターンの矛盾）：**
（普段の行動と特定条件での行動の落差）

**矛盾③（欲求の矛盾）：**
（「〜したいが〜したい」という相反する欲求）

**矛盾がキャラクターを動かす仕組み：**
（この矛盾がどのように行動の動機になるか）

**矛盾が「問い」とどう接続するか：**
（S7の核心の問いとの関係）

**矛盾が露わになる場面（具体的に）：**
（序盤・中盤・クライマックスの3場面）

**他キャラクターとの矛盾の相互作用：**
（相方・対立者がいることでこの矛盾がどう増幅されるか）

**「普通のキャラ」との違い：**
（このキャラが平均的な設計に陥らない理由）

---

## ■ 相方の性格設計

**X軸：** / **Y軸：**

**矛盾①：**
**矛盾②：**
**矛盾③：**

**矛盾が主人公の矛盾と「ぶつかる」または「共鳴する」方法：**
（2つの矛盾が組み合わさることで生まれるドラマ）

**矛盾が露わになる場面（具体的に）：**

**「普通のキャラ」との違い：**

---

## ■ 対立者の性格設計
（本敵B・偽敵Aなど複数いる場合はそれぞれ設計する）

**X軸：** / **Y軸：**

**矛盾①：**
**矛盾②：**
**矛盾③：**

**なぜ対立者が「悪」ではなく「別の答えを持つ者」に見えるか：**
（矛盾が対立者を人間的にする理由）

**対立者の矛盾が主人公の矛盾を「映す鏡」になる方法：**

**矛盾が露わになる場面（具体的に）：**

---

## ■ サブキャラの性格設計
（複数いる場合はそれぞれ設計する）

**X軸：** / **Y軸：**

**矛盾①：**
**矛盾②：**

**サブキャラの矛盾が主人公・相方の矛盾をどう照射するか：**

---

## ■ キャラクター間の矛盾マップ

各キャラクターの矛盾がどう絡み合うかを整理：

S10で設計した全キャラクターを縦・横に並べ、
それぞれの矛盾の組み合わせで「共鳴/衝突/対比/増幅」のいずれかを記入すること。
（人数に応じて行・列を追加すること）

| | 主人公の矛盾と | 相方の矛盾と | 対立者の矛盾と | サブキャラの矛盾と |
|---|------------|-----------|------------|---------------|
| 主人公 | ─ | | | |
| 相方 | | ─ | | |
| 対立者 | | | ─ | |
| サブキャラ | | | | ─ |

**最も大きな矛盾の衝突が起きる場面：**
（どのキャラの矛盾同士がぶつかり最大のドラマを生むか）

---

## ■ S12（トラウマ設計）への引き渡しパラメータ

S10で設計した全キャラクターの行を含めること。

| キャラ | 矛盾の核 | 矛盾の原因として想定されるトラウマの方向性 |
|------|--------|--------------------------------------|
| 主人公 | | |
| 相方 | | |
| 対立者（本敵B） | | |
| 対立者（偽敵A） | | |
| サブキャラ① | | |
| 相方の友人 | | |
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
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S11] X軸Y軸性格設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    prev = load_prev_outputs(novel_type)

    prompt = build_prompt(prev, novel_type)
    print("  性格設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# X軸Y軸性格設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s11_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s11_personality_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_性格設計")},
            "スキル":     {"rich_text": txt("S11_性格設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "X軸Y軸性格設計", result)

    print("[S11] 完了\n")
    print("  次のステップ: S12（トラウマ設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 12 --type {novel_type}")

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
