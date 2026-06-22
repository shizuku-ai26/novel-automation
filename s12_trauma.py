# -*- coding: utf-8 -*-
"""
S12：トラウマ設計スキル
呼び出し：python run_pipeline.py --skill 12 --type short
役割：S11の「矛盾の原因として想定されるトラウマ」を受け取り、
     トラウマを「歪んだ適応」として設計する。
     トラウマ自体ではなく「それがどう行動を歪めているか」が核心。

重要思想：
  弱いトラウマ設計：「幼少期に虐待された」→ 過去の説明で終わる
  強いトラウマ設計：「捨てられた→他人を試す」「支配された→感情を消す」
                   → 現在の行動パターンとして機能する

次ステップ：S13（キャラ欠落分析）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s12_trauma"


# ============================================================
# 歪んだ適応パターン定義
# ============================================================

DISTORTED_ADAPTATIONS = {
    "testing":      {
        "label":   "他者を試す",
        "trigger": "捨てられた・裏切られた",
        "desc":    "相手が本当に自分を愛しているか確かめるために、わざと困難な状況を作る",
        "drama":   "試すことで相手を追い詰め、結果的に関係を壊す自己成就予言",
    },
    "suppression":  {
        "label":   "感情を消す",
        "trigger": "感情を持つことで傷ついた・支配された",
        "desc":    "感情を持たないようにすることで傷つきを回避する。理性で全てを処理する",
        "drama":   "感情を消したはずなのに特定の相手にだけ感情が戻る瞬間",
    },
    "over_giving":  {
        "label":   "過剰献身",
        "trigger": "愛されなかった・必要とされなかった",
        "desc":    "相手の役に立つことでしか自分の存在価値を感じられない",
        "drama":   "尽くすほど相手が離れていく逆説・自分を消してしまう恐怖",
    },
    "control":      {
        "label":   "支配・管理",
        "trigger": "無力だった・コントロールを奪われた",
        "desc":    "周囲を管理することで「また裏切られない」状態を作ろうとする",
        "drama":   "管理することが相手の自由を奪い、愛を壊す",
    },
    "isolation":    {
        "label":   "自己孤立",
        "trigger": "関わることで誰かを傷つけた",
        "desc":    "自分が関わらなければ誰も傷つけないという信念から距離を置く",
        "drama":   "離れることで相手をもっと傷つける逆説",
    },
    "perfectionism":{
        "label":   "完璧主義",
        "trigger": "失敗したことで大切なものを失った",
        "desc":    "完璧であり続ければ失わなくて済むという信念",
        "drama":   "完璧を目指すほど人間関係が壊れていく",
    },
    "self_sacrifice":{
        "label":   "自己犠牲",
        "trigger": "自分より誰かを優先することが愛だと学んだ",
        "desc":    "自分を消すことで相手を幸せにできるという信念",
        "drama":   "自己犠牲が相手に罪悪感を与え、関係を壊す",
    },
    "anger_as_wall":{
        "label":   "怒りで壁を作る",
        "trigger": "傷つくより先に攻撃することで自分を守った",
        "desc":    "親密になりそうになると攻撃的になり相手を遠ざける",
        "drama":   "近づこうとする相手を傷つけることへの自己嫌悪",
    },
    "rescuing":     {
        "label":   "誰かを救おうとする",
        "trigger": "救えなかった経験・罪悪感",
        "desc":    "誰かを救うことで過去の罪悪感を償おうとする",
        "drama":   "救済が相手への押しつけになる・救えないと自分を責める",
    },
    "denial":       {
        "label":   "現実否定・逃避",
        "trigger": "現実が耐えられないものだった",
        "desc":    "現実を見ないことで傷つきを回避する。過去の記憶を書き換える",
        "drama":   "否定した現実が形を変えて戻ってくる",
    },
}


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s6":  base / "s06_gravity"     / f"s06_gravity_latest_{novel_type}.md",
        "s7":  base / "s07_philosophy"  / f"s07_philosophy_latest_{novel_type}.md",
        "s10": base / "s10_character"   / f"s10_character_latest_{novel_type}.md",
        "s11": base / "s11_personality" / f"s11_personality_latest_{novel_type}.md",
    }
    limits = {"s6": 1500, "s7": 1500, "s10": 1500, "s11": 1500}

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

    # 歪んだ適応テーブル
    adapt_table = "\n".join(
        f"・{k}（{v['label']}）：{v['trigger']} → {v['desc']} → ドラマ：{v['drama']}"
        for k, v in DISTORTED_ADAPTATIONS.items()
    )

    return f"""あなたはこの小説作品の「トラウマ設計者」です。
S11で設計した「矛盾の原因として想定されるトラウマの方向性」を受け取り、
トラウマを「歪んだ適応」として具体的に設計してください。

重要思想：
・トラウマ自体（過去の出来事）ではなく「それがどう現在の行動を歪めているか」が核心
・「歪んだ適応」は生存戦略として機能していた合理的な選択だった
・読者がトラウマに「共感」できるよう、普遍的な痛みに接続させる

【歪んだ適応パターン参考一覧（以下から選択・または独自設計）】
{adapt_table}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S11 矛盾の核・トラウマ方向性（引き渡しテーブル）】
{prev["s11_table"] if prev.get("s11_table") else prev["s11"]}

【S10 キャラクター設計（参考）】
{prev["s10"]}

【S7 哲学的問い（参考）】
{prev["s7"]}

【S6 関係性重力（参考）】
{prev["s6"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

# トラウマ設計書（S12）

---

S10で設計した全キャラクター（主人公・相方・対立者・サブキャラ等、S10/S11の人数に従う）について設計してください：

---

## ■ 主人公のトラウマ設計

**トラウマの出来事（過去）：**
（何が起きたか・いつ・誰との関係で）

**当時の「合理的な生存戦略」：**
（その状況でその行動・信念を採用したことがなぜ正しかったか）

**歪んだ適応（現在の行動パターン）：**
（上記の生存戦略が現在どんな形で行動に現れているか）

**「歪んだ適応」の具体的な行動例（3つ）：**
  ①
  ②
  ③

**トラウマが「問い」とどう接続するか：**
（S7の核心の問いとトラウマの関係）

**トラウマが「矛盾」とどう接続するか：**
（S11の矛盾①②③がトラウマから生まれる理由）

**トラウマが「露わになる瞬間」：**
（物語のどのシーンで、どんな刺激でトラウマが顕在化するか）

**トラウマの「回復」or「受容」の設計：**
（完全に癒えるのか・受容するのか・抱えたまま終わるのか）

**読者との接続点：**
（このトラウマがどんな普遍的な痛みに接続しているか）

---

## ■ 相方のトラウマ設計

**トラウマの出来事（過去）：**
**当時の「合理的な生存戦略」：**
**歪んだ適応（現在の行動パターン）：**
**具体的な行動例（3つ）：**①②③
**主人公のトラウマとどう「共鳴」または「衝突」するか：**
（2つのトラウマが組み合わさることで生まれるドラマ）
**トラウマが露わになる瞬間：**
**回復・受容の設計：**

---

## ■ 対立者のトラウマ設計
（本敵B・偽敵Aなど複数いる場合はそれぞれ設計する）

**トラウマの出来事（過去）：**
**当時の「合理的な生存戦略」：**
**歪んだ適応（現在の行動パターン）：**
**具体的な行動例（3つ）：**①②③
**対立者のトラウマが「どんでん返し構造」とどう機能するか：**
（S1のどんでん返しパターンにおいて対立者のトラウマはどんな役割を持つか）
**対立者を「悪」ではなく「傷ついた人間」として描くための設計：**

---

## ■ サブキャラのトラウマ設計
（複数いる場合はそれぞれ設計する）

**トラウマの出来事（過去）：**
**歪んだ適応（現在の行動パターン）：**
**サブキャラのトラウマが主人公のトラウマを「映す鏡」になる方法：**

---

## ■ トラウマ連鎖の設計

複数キャラのトラウマがどう連鎖・影響し合うかを設計：

**主人公のトラウマが相方を傷つける構造：**
（意図せず相方の傷を刺激する行動）

**相方のトラウマが主人公を傷つける構造：**

**この連鎖がどんでん返しでどう「見え方が変わる」か：**

---

## ■ S13（キャラ欠落分析）への引き渡しパラメータ

S10で設計した全キャラクターの行を含めること。

| キャラ | 歪んだ適応 | 「できないこと」の核心 | テーマとの欠落接続 |
|------|---------|-----------------|---------------|
| 主人公（碧） | | | |
| 相方（柚） | | | |
| 対立者（本敵B：久我） | | | |
| 対立者（偽敵A：三島） | | | |
| サブキャラ①（中根） | | | |
| 相方の友人（静） | | | |
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

    print("\n[S12] トラウマ設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  歪んだ適応パターン: {len(DISTORTED_ADAPTATIONS)}種（拡張可能）")

    prev = load_prev_outputs(novel_type)

    # fix③: S11のS12引き渡しテーブルはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s11_path = _Path(__file__).parent.parent / "output" / "s11_personality" \
               / f"s11_personality_latest_{novel_type}.md"
    if _s11_path.exists():
        _s11_full = _s11_path.read_text(encoding="utf-8")
        _idx = _s11_full.rfind("## ■ S12（トラウマ設計）への引き渡しパラメータ")
        prev["s11_table"] = _s11_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s11_table"] = ""

    prompt = build_prompt(prev)
    print("  トラウマ設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# トラウマ設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s12_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s12_trauma_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_トラウマ設計")},
            "スキル":     {"rich_text": txt("S12_トラウマ設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "トラウマ設計", result)

    print("[S12] 完了\n")
    print("  次のステップ: S13（キャラ欠落分析）")
    print(f"  コマンド例: python run_pipeline.py --skill 13 --type {novel_type}")

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
