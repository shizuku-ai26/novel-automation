# -*- coding: utf-8 -*-
"""
S9：テーマ設計スキル
呼び出し：python run_pipeline.py --skill 9 --type short
役割：「主張」ではなく「揺らぎ」としてテーマを設計する。
     S7（哲学的問い）とS8（感情設計）を合流させ、
     テーマが物語全体に浸透する構造を設計する。

重要思想：
  弱いテーマ：「戦争は悪」→ 答えが先に見えている
  強いテーマ：「他人の痛みを共有したら戦争は消えるか？」→ 揺らぎが残る

出力：
  ・大テーマ（作品全体を貫く揺らぎ）
  ・中テーマ（各フェーズで問い直されるテーマ）
  ・テーマの体現者設計
  ・S10（キャラクター設計）へのパラメータ
"""

import re
import unicodedata
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR    = Path(__file__).parent.parent / "output" / "s09_theme"
MID_THEME_DIR = Path(__file__).parent.parent / "input"


# ============================================================
# テーマ強度チェックリスト
# ============================================================

THEME_STRENGTH = """
【強いテーマ（揺らぎ）の条件】
✅ 問いの形をしている（答えが見えない）
✅ 登場人物が「異なる答え」を体現している
✅ どんでん返しでテーマの意味が書き換わる
✅ 読後も答えが出ないまま揺れ続ける
✅ 読者が自分の経験に照らして考えられる
✅ 物語の全シーンがテーマと接続している

【弱いテーマ（主張）の例 → 避けるべき】
❌ 「愛は世界を救う」→ 答えが先に見えている
❌ 「人は一人では生きられない」→ 説教になる
❌ 「友情の大切さ」→ テーマではなく教訓
❌ 「諦めなければ夢は叶う」→ メッセージが固定
❌ 「正義は必ず勝つ」→ 世界観が単純

【テーマの「揺らぎ」を保つ技法】
・主人公とサブキャラが正反対の答えを体現する
・序盤の「正解」が終盤で「間違い」に見える
・読者が「どちらが正しいか」を判断できない設計
・テーマを登場人物に直接語らせない（行動で示す）
"""


# ============================================================
# 中テーマ型：完全ファイル駆動ロード
#   input/type01.txt 〜 input/type24.txt を実行ごとに読み込む
#   ・ファイル名の連番（01,02…）はソート順のみに使用
#   ・タイプID・名前は必ずファイル内容の「【タイプXX】「名前」」から取得
#   ・【タイプ1】【タイプ２】【タイプ07】など全角・半角・ゼロパディング全対応
# ============================================================

# 期待するタイプIDの範囲（1〜24）
_EXPECTED_TYPE_IDS = set(range(1, 25))


def _parse_type_file(content: str, filepath_name: str) -> tuple:
    """
    ファイル内容から (type_id, name, summary) を抽出する。

    1行目フォーマット: 【タイプXX】「名前」
      - XX は半角・全角・ゼロパディング全て対応（NFKC正規化で統一）
    summaryフォーマット: ■ で始まる最初の行（50字以内）
    """
    lines = content.splitlines()
    first_line = unicodedata.normalize('NFKC', lines[0].strip()) if lines else ""

    # type_id: 正規化後の【タイプXX】から取得
    type_id = None
    m_id = re.search(r'【タイプ(\d+)】', first_line)
    if m_id:
        type_id = int(m_id.group(1))

    # name: 正規化後の「」内を取得
    name = filepath_name  # フォールバック
    m_name = re.search(r'「(.+?)」', first_line)
    if m_name:
        name = m_name.group(1)

    # summary: ■で始まる最初の行（50字以内）
    summary = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("■"):
            summary = unicodedata.normalize('NFKC', stripped[1:].strip())[:50]
            break

    return type_id, name, summary


def _load_mid_theme_types() -> dict:
    """
    input/ 配下の type[0-9][0-9].txt を全て読み込み、
    タイプIDをキーとした dict を返す。実行ごとにロード状況を表示。

    ファイル命名規則 : type{連番2桁}.txt（ソート用・例: type01.txt〜type24.txt）
    タイプID取得元   : ファイル内容の「【タイプXX】」（ファイル名は参照しない）
    期待範囲        : タイプ1〜24（揃っていない場合は WARN 表示）
    """
    types   = {}
    loaded  = []
    errors  = []

    if not MID_THEME_DIR.exists():
        print(f"  [WARN] inputディレクトリが見つかりません → {MID_THEME_DIR}")
        print(f"         type01.txt〜type24.txt を配置してください。")
        return types

    for filepath in sorted(MID_THEME_DIR.glob("type[0-9][0-9].txt")):
        try:
            content = filepath.read_text(encoding="utf-8")
            type_id, name, summary = _parse_type_file(content, filepath.name)

            if type_id is None:
                errors.append(f"{filepath.name}: 1行目に【タイプXX】が見つかりません")
                continue
            if type_id in types:
                errors.append(f"{filepath.name}: タイプID={type_id} が重複しています")
                continue

            types[type_id] = {"name": name, "summary": summary, "detail": content}
            loaded.append(type_id)

        except Exception as e:
            errors.append(f"{filepath.name}: {e}")

    # ── ロード結果サマリー表示 ──────────────────────────────
    missing = sorted(_EXPECTED_TYPE_IDS - set(types.keys()))

    print(f"  [中テーマ型] {len(types)}種ロード完了（期待値: 24種）")
    if loaded:
        print(f"           登録済み: {sorted(loaded)}")
    if missing:
        print(f"  [WARN]   未登録  : {missing}  ← 該当 type{{nn}}.txt を input/ に配置")
    if errors:
        for e in errors:
            print(f"  [ERROR]  {e}")

    return types


# モジュール読み込み時に1回だけロード
MID_THEME_TYPES = _load_mid_theme_types()
MID_THEME_KEYS  = list(MID_THEME_TYPES.keys())

# ============================================================
# Pass 1：中テーマ型の選択のみ（タイプ番号だけを返す）
# ============================================================

def build_type_selection_prompt(prev: dict, novel_type: str,
                                 last_used: int = None) -> str:
    """どのタイプを選ぶかだけを決めるための軽量プロンプト"""
    import json as _json
    _used_file = OUTPUT_DIR / f"s09_used_type_{novel_type}.json"
    if last_used is None:
        try:
            last_used = _json.loads(
                _used_file.read_text(encoding="utf-8")
            ).get("last_used_type")
        except Exception:
            pass

    types_text = "\n".join(
        f"  タイプ{k:02d}：{v['name']}　→ {v['summary'][:40]}"
        + (" 【前回使用・今回選択不可】" if k == last_used else "")
        for k, v in MID_THEME_TYPES.items()
    )
    exclusion = (
        f"\n【禁止】タイプ{last_used:02d}は前回使用済み。今回は絶対に選ばないこと。\n"
        if last_used else ""
    )

    return f"""以下の作品情報を読み、最も適切な中テーマ型を1つ選び、
タイプ番号だけを「タイプ: XX」の形式で回答してください。
理由や説明は不要です。番号1行のみ出力してください。

{exclusion}
【中テーマ型一覧】
{types_text}

【S7哲学的問い（抜粋）】
{prev["s7"]}

【S8感情設計（抜粋）】
{prev["s8"]}

【S1価値観反転（抜粋）】
{prev["s1"]}
"""


def _parse_selected_type(response: str) -> int | None:
    """Pass1レスポンスからタイプ番号を抽出する"""
    import re
    # 有効範囲：1〜24（MID_THEME_TYPESが空でも動作）
    valid = set(MID_THEME_TYPES.keys()) if MID_THEME_TYPES else set(range(1, 25))
    # 「タイプ: XX」「タイプ05」「タイプ：5」等
    m = re.search(r'タイプ[：: ]*([0-9]+)', response)
    if m:
        tid = int(m.group(1))
        if tid in valid:
            return tid
    # フォールバック：数字だけのレスポンスにも対応
    m2 = re.search(r'(?<![0-9])([0-9]{1,2})(?![0-9])', response)
    if m2:
        tid = int(m2.group(1))
        if tid in valid:
            return tid
    return None



# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s1": base / "s01_plot_twist"    / f"s01_twist_latest_{novel_type}.md",
        "s2": base / "s02_submission"    / f"s02_submission_latest_{novel_type}.md",
        "s6": base / "s06_gravity"       / f"s06_gravity_latest_{novel_type}.md",
        "s7": base / "s07_philosophy"    / f"s07_philosophy_latest_{novel_type}.md",
        "s8": base / "s08_emotion"       / f"s08_emotion_latest_{novel_type}.md",
    }
    limits = {"s1": 400, "s2": 400, "s6": 400, "s7": 1200, "s8": 800}

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

def build_prompt(prev: dict, contest_key: str, novel_type: str,
                 selected_type_id: int = None,
                 selected_type_detail: str = None) -> str:

    contest_note = ""
    if contest_key == "note":
        contest_note = "※note：テーマは「感情」に溶け込ませる。主張せず、読者が感じ取る設計。"
    elif contest_key == "kakugawa_chara":
        contest_note = "※角川：テーマはキャラクターの「行動の動機」として自然に埋め込む。"
    elif contest_key == "kakuyomu":
        contest_note = "※カクヨム：テーマは薄く・エンタメを妨げない程度に。明示しない。"
    elif contest_key == "everystory":
        contest_note = "※エブリスタ：テーマより感情爆発を優先。テーマは背景に徹する。"

    # ── 選択済みタイプのフルテキストを使う（Pass2）、なければ一覧表示 ──
    if selected_type_id and selected_type_detail:
        type_info = MID_THEME_TYPES.get(selected_type_id, {})
        types_text = (
            f"【選択済み中テーマ型：タイプ{selected_type_id:02d}「{type_info.get('name','')}」】\n"
            f"以下の型定義を**全文熟読**した上で中テーマを設計してください。\n\n"
            f"{selected_type_detail}"
        )
        _exclusion_note = ""
    else:
        import json as _json
        _used_file = OUTPUT_DIR / f"s09_used_type_{novel_type}.json"
        _last_used = None
        try:
            _last_used = _json.loads(_used_file.read_text(encoding="utf-8")).get("last_used_type")
        except Exception:
            pass
        types_text = "\n".join(
            f"  タイプ{k:02d}：{v['name']}　→ {v['summary'][:40]}"
            + (" 【前回使用・今回選択不可】" if k == _last_used else "")
            for k, v in MID_THEME_TYPES.items()
        )
        _exclusion_note = (
            f"\n【重要】タイプ{_last_used:02d}は前回使用済みです。今回は必ず別のタイプを選択してください。\n"
            if _last_used else ""
        )

    return f"""あなたはこの小説作品の「テーマ設計者」です。
S7（哲学的問い）とS8（感情設計）を合流させ、
作品の大テーマ・中テーマを「揺らぎ」として設計してください。

{THEME_STRENGTH}

【中テーマ型一覧（いずれか1つを選択して中テーマを設計してください）】
{types_text}
{_exclusion_note}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S7哲学的問い（抜粋）】
{prev["s7"]}

【S8感情設計（抜粋）】
{prev["s8"]}

【S6関係性重力（抜粋）】
{prev["s6"]}

【S1価値観反転（抜粋）】
{prev["s1"]}

【S2投稿形態（参考）】
{prev["s2"]}

{contest_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

## ■ 大テーマの確定

**大テーマ（揺らぎの形で・30文字以内）：**
（「〜か？」または「〜と〜の間で」という形が理想）

**大テーマが「揺らぎ」である理由：**
（強いテーマの条件のうち、どれを満たしているか）

**大テーマの「正反対の答え」：**
・YES側（〜だ）：
・NO側（〜ではない）：
・物語はどちらにも決着をつけない理由：

---

## ■ 中テーマの設計（2〜3本）

### 中テーマ①
**採用した中テーマ型：**（タイプXX：名前）
**選定理由：**（この作品とこのタイプの親和性）
**テーマ：**
**役割：**（大テーマを支える / 対比する / 深化させる）
**物語のどのフェーズで機能するか：**
**体現するキャラクター：**

### 中テーマ②
**テーマ：**
**役割：**
**物語のどのフェーズで機能するか：**
**体現するキャラクター：**

### 中テーマ③（任意）
**テーマ：**
**役割：**

---

## ■ テーマの体現者設計

各登場人物がテーマのどの「立場」を体現するかを設計してください。

| キャラクター | テーマへの立場 | 体現する答え | 転換点 |
|------------|------------|-----------|------|
| 主人公 | | YES寄り / NO寄り / 揺れる | |
| 相方 | | | |
| 敵または対立者 | | | |
| サブキャラ | | | |

---

## ■ テーマの浸透設計

テーマが物語に「埋め込まれる」方法を設計してください。

**テーマを語らせない3つのルール：**
（登場人物にテーマを直接語らせないための具体的な禁止事項）
  ①
  ②
  ③

**テーマが最も強く「滲み出る」シーン（3つ）：**
（説明なしにテーマが伝わる具体的な場面・行動・台詞）
  場面①：
  場面②：
  場面③（クライマックス）：

**テーマと感情波形の連動：**
（S8の感情高低差のどの瞬間にテーマが最も強く機能するか）

---

## ■ どんでん返しとテーマの接続

**転（75%）でテーマがどう「書き換わる」か：**
（どんでん返し前後でテーマの意味がどう変化するか）

**「意味の書き換え」の具体的な内容：**
（同じ出来事が全く別のテーマ的意味を持つ瞬間）

---

## ■ テーマと読後感の接続

**大テーマが残すことで生まれる読後感：**
（S8で確定した読後感がテーマの「揺らぎ」によってどう深まるか）

**読後に読者の胸に残る「問いの残滓」：**
（答えは出ないまま、読者が持ち帰る問い）

---

## ■ S10（キャラクター設計）への引き渡しパラメータ

**主人公が体現すべきテーマの「欠落」：**
（主人公はテーマのどの部分を体現できていない存在か）

**相方が主人公のテーマの「欠落」を補う方法：**

**物語を通じて主人公のテーマへの答えがどう変化するか：**
（序盤の答え → 中盤の揺らぎ → 終盤の着地）

---

## ■ テーマの「平均化」回避チェック

**このコンテストで量産されがちなテーマのパターン：**
（3つ列挙）

**この作品のテーマがそれらと差別化できる理由：**
（S1価値観反転・S6重力・S7問いとの組み合わせによる固有性）
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

    print("\n[S9] テーマ設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    # ── 前ステップ出力読み込み ────────────────
    prev = load_prev_outputs(novel_type)

    # ── S1事前決定タイプの確認（あればPass1スキップ） ────
    import json as _json2
    _pre_type_path = Path(__file__).parent.parent / "output" / "s01_plot_twist" / f"pre_type_{novel_type}.json"
    s01_pre_id = None
    if _pre_type_path.exists():
        try:
            _pre = _json2.loads(_pre_type_path.read_text(encoding="utf-8"))
            _pid = _pre.get("type_id")
            if _pid and _pid in MID_THEME_TYPES:
                s01_pre_id = _pid
                print(f"  [S1事前決定] タイプ{s01_pre_id:02d}「{MID_THEME_TYPES[s01_pre_id]['name']}」→ Pass1スキップ")
        except Exception as _e:
            print(f"  [WARN] pre_type読み込みエラー: {_e}")

    # ── Pass 1：型選択（S1事前決定がなければ実行） ─────
    if s01_pre_id:
        selected_id = s01_pre_id
        type_name   = MID_THEME_TYPES[selected_id]["name"]
        type_detail = MID_THEME_TYPES[selected_id]["detail"]
        print(f"  [Pass 1] スキップ（S1事前決定: タイプ{selected_id:02d}「{type_name}」）")
    else:
        print("  [Pass 1] 中テーマ型を選択中...")
        p1_prompt   = build_type_selection_prompt(prev, novel_type)
        p1_result   = call_claude_sonnet(p1_prompt)
        selected_id = _parse_selected_type(p1_result)

        if selected_id:
            type_name   = MID_THEME_TYPES[selected_id]["name"]
            type_detail = MID_THEME_TYPES[selected_id]["detail"]
            print(f"  [Pass 1] 選択タイプ: タイプ{selected_id:02d}「{type_name}」")
        else:
            print(f"  [WARN] タイプ番号が解析できませんでした（Pass1結果: {p1_result[:50]}）")
            print("         タイプ一覧モードにフォールバックします")
            selected_id = None
            type_detail = None

    # ── Pass 2：フルテキストで本設計 ─────────
    print("  [Pass 2] フルテキストで中テーマ設計中（Claude Sonnet）...")
    prompt = build_prompt(prev, contest_key, novel_type, selected_id, type_detail)
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    content = f"""# テーマ設計
実行日時：{timestamp}
小説タイプ：{novel_type}
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 使用タイプを次回の除外用に保存 ──────────────────────
    import json as _json, re as _re
    _m = _re.search(r'採用した中テーマ型[：:].*?タイプ[^0-9]*([0-9]+)', result)
    if _m:
        _used_id = int(_m.group(1))
        _used_file = OUTPUT_DIR / f"s09_used_type_{novel_type}.json"
        _used_file.write_text(
            _json.dumps({"last_used_type": _used_id, "timestamp": timestamp}, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"  [OK] 使用タイプ保存: タイプ{_used_id:02d} → 次回選択不可")

    filepath = OUTPUT_DIR / f"s09_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s09_theme_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_テーマ設計")},
            "スキル":     {"rich_text": txt("S9_テーマ設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "テーマ設計", result)

    print("[S9] 完了\n")
    print("  次のステップ: S10（キャラクター設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 10 --type {novel_type}")

    return {
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
