# -*- coding: utf-8 -*-
"""
S31：既視感除去＋文章量調整スキル
呼び出し：python run_pipeline.py --skill 31 --type short --target 50000

処理フロー：
  PASS1  Gemini Pro   ── 全セクション一括読み込み → 繰り返しパターンリスト生成（1回）
  PASS2  Claude Sonnet── パターンリスト注入 + 比例圧縮（セクション×9）
                         本文 + 変更サマリーを同時出力（マーカー区切り）
  PASS3  差分レポート集約 → s31_diff_report_{timestamp}.md

--target ルール：
  現在 > 目標 → 削る（必須）優先順：モノローグ → セリフ → 地の文
  現在 < 目標 → 伸ばす（最小限・最終手段）
  出力文字数は必ず --target 以内
"""

import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import load_config, call_claude_sonnet
from common.gemini_utils import call_gemini_thinking
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s31_trim"
S30_DIR    = Path(__file__).parent.parent / "output" / "s30_dialogue_enhance"

SECTIONS = [
    {"id": 0, "name": "プロローグ"},
    {"id": 1, "name": "第1章"},
    {"id": 2, "name": "第2〜3章"},
    {"id": 3, "name": "第4〜5章"},
    {"id": 4, "name": "ミッドポイント"},
    {"id": 5, "name": "第6〜7章"},
    {"id": 6, "name": "転"},
    {"id": 7, "name": "第9〜10章"},
    {"id": 8, "name": "エピローグ"},
]

# Phase2出力のマーカー
_TEXT_START  = "===TEXT_START==="
_TEXT_END    = "===TEXT_END==="
_REPORT_START = "===REPORT_START==="
_REPORT_END   = "===REPORT_END==="


# ============================================================
# S30ファイル読み込み
# ============================================================

def _extract_body(text: str) -> str:
    """ヘッダー（#行・実行日時・文字数・---）を除いた本文を返す"""
    lines = text.splitlines()
    body_lines = []
    in_header = True
    for line in lines:
        if in_header:
            if line.strip() == "---":
                in_header = False
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def load_s30_sections(novel_type: str) -> list[dict]:
    """
    S30出力を読み込んでセクション情報リストを返す。
    探索優先：s30_{novel_type}_{n}_latest.md
           → s30_short_{n}_latest.md
           → s30_short_{n}_*.md の最新タイムスタンプ
    """
    results = []
    for sec in SECTIONS:
        n, name = sec["id"], sec["name"]
        path = None
        for candidate in [
            S30_DIR / f"s30_{novel_type}_{n}_latest.md",
            S30_DIR / f"s30_short_{n}_latest.md",
            *(sorted(S30_DIR.glob(f"s30_short_{n}_*.md"))[-1:]),
        ]:
            if candidate and Path(candidate).exists():
                path = Path(candidate)
                break

        if path is None:
            print(f"  [WARN] Section {n}「{name}」: S30ファイルが見つかりません")
            results.append({"id": n, "name": name, "content": "", "chars": 0})
            continue

        content = _extract_body(path.read_text(encoding="utf-8"))
        chars   = len(content.replace("\n","").replace("\r","").replace(" ",""))
        results.append({"id": n, "name": name, "content": content, "chars": chars})
        print(f"  [OK] Section {n}「{name}」: {chars:,}字  ({path.name})")
    return results


# ============================================================
# 目標文字数の比例配分
# ============================================================

def calculate_targets(sections: list[dict], total_target: int) -> list[dict]:
    total = sum(s["chars"] for s in sections)
    if total == 0:
        print("  [ERROR] 全セクションの文字数が0。S30ファイルを確認してください。")
        return sections
    print(f"\n  [目標配分] {total:,}字 → {total_target:,}字 "
          f"（{(total - total_target) / total * 100:.1f}%削減）\n")
    for s in sections:
        s["target"] = max(100, int(s["chars"] / total * total_target)) if s["chars"] > 0 else 0
    return sections


# ============================================================
# PASS 1: Gemini Pro で全セクション横断の既視感検出
# ============================================================

def build_pass1_prompt(all_text: str) -> str:
    return f"""あなたはこの小説の編集者です。
以下の全セクション（Section 0〜8）を通して読み、
**作品全体で繰り返し使われている表現・パターン**を検出してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【検出対象】
① 同一または類似のフレーズ（3回以上使用）
   例：「指先が震える」「白い壁に吸い込まれる」「一秒だけ」

② 同じ文末パターンの連続
   例：「〜いた。〜いた。〜いた。」が3文以上続く箇所

③ 繰り返されるモノローグパターン
   例：「〜している。/〜していない。/〜ている。」の詩的コメント構造

④ 同じ動作・状態の重複描写
   例：「手が震える」描写がSection0・1・3・7 で各複数回

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【出力形式】
以下の形式で出力してください。後工程（各セクション圧縮）で直接使います。

## 【繰り返しパターン検出結果】

### 高頻度（5回以上）
- 「（表現）」→ Section X, Y, Z で計N回
  推奨アクション：（削除 or 1〜2回に絞る or 表現をバリエーション化）

### 中頻度（3〜4回）
- 「（表現）」→ Section X, Y で計N回
  推奨アクション：...

### 文末・構造パターン
- （パターンの説明）→ 該当Section：X, Y
  推奨アクション：...

### モノローグ構造パターン
- （パターンの説明）→ 該当Section：X, Y
  推奨アクション：...

## 【各セクションへの引き渡しメモ】
Section 0：（このセクションで特に注意すべき繰り返し）
Section 1：...
（Section 2〜8も同様）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【全テキスト】

{all_text}
"""


def run_pass1(sections: list[dict], config: dict) -> str:
    """全セクションを結合してGemini Proで既視感検出"""
    print("\n[PASS1] 既視感検出（Gemini Pro）開始...")

    # 全セクション結合
    all_text = "\n\n".join(
        f"=== Section {s['id']}：{s['name']} ===\n{s['content']}"
        for s in sections if s["chars"] > 0
    )

    prompt  = build_pass1_prompt(all_text)
    result  = call_gemini_thinking(prompt, model="gemini-2.5-pro", config=config)

    # パターンレポートを保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = OUTPUT_DIR / f"s31_patterns_{ts}.md"
    report_path.write_text(
        f"# 既視感パターン検出レポート\n実行日時：{ts}\n\n---\n\n{result}",
        encoding="utf-8"
    )
    print(f"  [OK] パターンレポート保存: {report_path.name}")
    print(f"  [INFO] 検出文字数: {len(result):,}字")
    return result


# ============================================================
# PASS 2: Claude Sonnet でセクション別圧縮
# ============================================================

def build_pass2_prompt(section_name: str, content: str,
                       current_chars: int, target_chars: int,
                       patterns_report: str) -> str:
    reduction_rate = (current_chars - target_chars) / current_chars * 100
    return f"""あなたはこの小説の編集者です。
セクション「{section_name}」を **{target_chars}字以内** に圧縮してください。
現在 {current_chars:,}字 → 目標 {target_chars:,}字（約{reduction_rate:.0f}%削減）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【PASS1で検出された繰り返しパターン（全体横断）】
以下のパターンをこのセクションから積極的に削除・修正してください。

{patterns_report}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【削除・圧縮の優先順位】

① 同じ表現・文章の削除または言い換え（最優先）
   ・同一または類似のフレーズが複数箇所に出てくる場合、後出を削除または別の言い回しに変更
   ・例：「指先が冷たい」が3回以上 → 後の2回を別の表現か削除

② モノローグ・短文の統合
   ・地の文の短文連続（体言止め・1行1文が連続する箇所）をまとめられるものは1文にまとめる
   ・例：「震えている。止まらない。指先だけが動く。」→「震えは指先に残ったまま、止まらない。」
   ・ただし意図的なリズム（転・クライマックスの短文連打）は維持する

③ 意味が通じにくい短文の補足または省略
   ・文脈なしに意味が通じない断片的な文は補足説明を加えるか省略する
   ・例：「音が残る。」（何の音か不明）→「金属音が、廊下に残る。」または削除

④ ▷キャラ名：「セリフ」の短縮・削除
   ・▷キャラ名：「」 の形式は必ず維持
   ・冗長・重複するセリフを削除または統合

⑤ 地の文の反復・過剰描写を圧縮
   ・同じ動作・状態の重複描写を1回にまとめる

⑥ 伸ばし（最終手段・目標を大幅に下回った場合のみ）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【厳守事項】
  ✅ ▷キャラ名：「セリフ」の形式を必ず維持
  ✅ ====区切り線とセクションヘッダーを維持
  ✅ 物語の因果・流れを壊さない
  ✅ 冒頭シーンと結末シーンを必ず保持
  ❌ 出力は {target_chars}字を絶対に超えない

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【入力テキスト】
{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【出力形式】※マーカーを正確に出力してください

{_TEXT_START}
（圧縮後の本文テキストのみ。ヘッダー行不要。====区切り線から始める）
{_TEXT_END}
{_REPORT_START}
## 変更サマリー：{section_name}
- 削除したモノローグ行：約N件
- 短縮・削除したセリフ：約N件
- 修正した繰り返し表現：約N件（具体的な表現を列挙）
- 主な削除内容：（代表的な削除箇所を3〜5個）
{_REPORT_END}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【マーカー出力の絶対遵守】
以下の4つのマーカーを必ず正確に出力すること。
1行に単独で出力し、前後に余分な文字を入れないこと。

  {_TEXT_START}    ← 本文の開始
  {_TEXT_END}      ← 本文の終了
  {_REPORT_START}  ← サマリーの開始
  {_REPORT_END}    ← サマリーの終了

マーカーが1つでも欠けると出力が無効になります。
どれほど本文が長くても、必ずこの4つで囲って出力すること。
"""


def _parse_pass2_output(raw: str) -> tuple[str, str]:
    """
    PASS2出力からテキストと変更サマリーを分離して返す。
    マーカーが崩れた場合はテキスト全体を本文として扱う。
    """
    text_match   = re.search(
        rf"{re.escape(_TEXT_START)}\s*(.*?)\s*{re.escape(_TEXT_END)}",
        raw, re.DOTALL
    )
    report_match = re.search(
        rf"{re.escape(_REPORT_START)}\s*(.*?)\s*{re.escape(_REPORT_END)}",
        raw, re.DOTALL
    )

    text   = text_match.group(1).strip()   if text_match   else raw.strip()
    report = report_match.group(1).strip() if report_match else "（変更サマリーの抽出に失敗）"

    if not text_match:
        print("    [WARN] TEXTマーカーが見つかりません。出力全体を本文として使用します。")

    return text, report


def trim_section(section: dict, patterns_report: str,
                 retry_max: int = 2) -> tuple[str, str]:
    """
    Claude Sonnet でセクションを圧縮。
    目標超過の場合は最大 retry_max 回再試行。
    (trimmed_text, change_report) を返す。
    """
    name          = section["name"]
    content       = section["content"]
    current_chars = section["chars"]
    target_chars  = section["target"]

    print(f"  圧縮中: 「{name}」 {current_chars:,}字 → 目標{target_chars:,}字")

    last_text = last_report = ""
    for attempt in range(retry_max + 1):
        prompt = build_pass2_prompt(
            name, content, current_chars, target_chars, patterns_report
        )
        raw    = call_claude_sonnet(prompt)
        text, report = _parse_pass2_output(raw)

        result_chars = len(text.replace("\n","").replace("\r","").replace(" ",""))
        last_text, last_report = text, report

        print(f"    → 試行{attempt + 1}: {result_chars:,}字", end="")
        if result_chars <= int(target_chars * 1.05) and result_chars >= int(target_chars * 0.85):
            print(" ✅")
            return text, report
        elif result_chars > int(target_chars * 1.05):
            print(f" ⚠️ 超過（目標{target_chars:,}字）")
            if attempt < retry_max:
                print("    再試行します...")
                content       = text
                current_chars = result_chars
        else:
            print(f" ❌ 削りすぎ（目標の{result_chars/target_chars:.0%}、元文章を維持）")
            return content, ""  # 過剰削減の場合は元文章を返す

    final_chars = len(last_text.replace("\n","").replace("\r","").replace(" ",""))
    print(f"  [WARN] 「{name}」: {final_chars:,}字で確定（目標{target_chars:,}字）")
    return last_text, last_report


# ============================================================
# ファイル保存
# ============================================================

def save_section(section: dict, trimmed: str,
                 novel_type: str, timestamp: str) -> None:
    n    = section["id"]
    name = section["name"]
    actual = len(trimmed.replace("\n","").replace("\r","").replace(" ",""))

    body = (f"# 文章量調整済み：{name}\n"
            f"実行日時：{timestamp}\n"
            f"目標文字数：{section['target']:,}字\n"
            f"実際文字数：{actual:,}字\n\n---\n\n{trimmed}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"s31_{novel_type}_{n}_{timestamp}.md").write_text(body, encoding="utf-8")
    (OUTPUT_DIR / f"s31_{novel_type}_{n}_latest.md").write_text(body, encoding="utf-8")
    print(f"  [OK] Section {n}「{name}」: {actual:,}字")


def save_all(sections_out: list[dict], novel_type: str, timestamp: str,
             total_target: int) -> None:
    total_actual = sum(s["actual_chars"] for s in sections_out)
    lines = [
        f"# S31 全セクション統合（{novel_type}）",
        f"実行日時：{timestamp}",
        f"目標文字数：{total_target:,}字",
        f"実際文字数：{total_actual:,}字", "",
    ]
    for s in sections_out:
        lines += [
            f"\n============================================================",
            f"[Section {s['id']}：{s['name']}]",
            f"============================================================\n",
            s["trimmed"],
        ]
    path = OUTPUT_DIR / f"s31_all_{novel_type}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [OK] All: {path.name}  合計{total_actual:,}字")


def save_diff_report(sections_out: list[dict], sections_in: list[dict],
                     patterns_report: str,
                     novel_type: str, timestamp: str,
                     total_target: int) -> None:
    total_before = sum(s["chars"]        for s in sections_in  if s["chars"] > 0)
    total_after  = sum(s["actual_chars"] for s in sections_out)
    reduction    = (total_before - total_after) / total_before * 100

    lines = [
        f"# S31 差分レポート（{novel_type}）",
        f"実行日時：{timestamp}",
        f"",
        f"## サマリー",
        f"| | 文字数 |",
        f"|---|---|",
        f"| 処理前（S30） | {total_before:,}字 |",
        f"| 処理後（S31） | {total_after:,}字 |",
        f"| 目標          | {total_target:,}字 |",
        f"| 削減量        | {total_before - total_after:,}字（{reduction:.1f}%）|",
        f"| 目標達成      | {'✅ OK' if total_after <= total_target else '⚠️ 超過'} |",
        f"",
        f"## セクション別 文字数変化",
        f"| Section | セクション名 | 処理前 | 処理後 | 目標 | 削減率 |",
        f"|---|---|---|---|---|---|",
    ]

    in_map = {s["id"]: s for s in sections_in}
    for s in sections_out:
        before = in_map[s["id"]]["chars"]
        after  = s["actual_chars"]
        target = s["target_chars"]
        rate   = (before - after) / before * 100 if before > 0 else 0
        ok     = "✅" if after <= int(target * 1.05) else "⚠️"
        lines.append(
            f"| {s['id']} | {s['name']} | {before:,} | {after:,} | {target:,} | {rate:.1f}% {ok} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## PASS1 既視感パターン検出結果",
        f"",
        patterns_report,
        f"",
        f"---",
        f"",
        f"## セクション別 変更サマリー",
        f"",
    ]
    for s in sections_out:
        lines += [f"### Section {s['id']}：{s['name']}", f"", s["change_report"], f""]

    path = OUTPUT_DIR / f"s31_diff_report_{timestamp}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [OK] 差分レポート: {path.name}")


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    novel_type   = config.get("novel_type", "short")
    total_target = int(config.get("target", 50000))
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M")

    print(f"\n[S31] 既視感除去＋文章量調整 開始")
    print(f"  小説タイプ : {novel_type}")
    print(f"  目標文字数 : {total_target:,}字")

    # ── S30読み込み・目標配分 ─────────────────────────────
    print("\n  S30ファイル読み込み中...")
    sections = load_s30_sections(novel_type)
    sections = calculate_targets(sections, total_target)

    # ── PASS1: 全横断・既視感検出（Gemini Pro）──────────────
    patterns_report = run_pass1(sections, config)

    # ── PASS2: セクション別圧縮（Claude Sonnet）─────────────
    print("\n[PASS2] セクション別圧縮（Claude Sonnet）開始...")
    sections_out = []
    for sec in sections:
        if sec["chars"] == 0:
            print(f"  [SKIP] Section {sec['id']}「{sec['name']}」")
            continue

        trimmed, change_report = trim_section(sec, patterns_report)
        actual_chars = len(trimmed.replace("\n","").replace("\r","").replace(" ",""))

        save_section(sec, trimmed, novel_type, timestamp)
        sections_out.append({
            "id":           sec["id"],
            "name":         sec["name"],
            "trimmed":      trimmed,
            "actual_chars": actual_chars,
            "target_chars": sec["target"],
            "change_report": change_report,
        })

    # ── PASS3: 統合ファイル＋差分レポート ──────────────────
    print("\n[PASS3] ファイル集約...")
    if sections_out:
        save_all(sections_out, novel_type, timestamp, total_target)
        save_diff_report(sections_out, sections, patterns_report,
                         novel_type, timestamp, total_target)

    # ── サマリー ────────────────────────────────────────────
    total_actual = sum(s["actual_chars"] for s in sections_out)
    print(f"\n[S31] 完了")
    print(f"  処理前: {sum(s['chars'] for s in sections if s['chars']>0):,}字")
    print(f"  処理後: {total_actual:,}字  目標: {total_target:,}字 "
          f"({'✅ OK' if total_actual <= total_target else '⚠️ 超過'})")
    print(f"\n  次のステップ: S32（整合性チェック）")
    print(f"  コマンド例: python run_pipeline.py --skill 32 --type {novel_type}")

    return {
        "sections":     sections_out,
        "total_actual": total_actual,
        "total_target": total_target,
        "timestamp":    timestamp,
    }


# ============================================================
# エントリポイント
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",   default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--target", default=50000, type=int,
                        help="目標文字数（上限・超過NG）")
    args = parser.parse_args()
    _config             = load_config()
    _config["novel_type"] = args.type
    _config["target"]   = args.target
    run(config=_config)
