# -*- coding: utf-8 -*-
"""
S32：整合性チェック準備スキル
呼び出し：python run_pipeline.py --skill 32 --type short

処理内容：
  S31出力ファイルを読み込み、Claude Opusへの手動投入に必要な
  2つのファイルを生成する。

  ① s32_input_{novel_type}_{timestamp}.md
     → Opusチャットに「添付」するファイル（全セクション統合テキスト）

  ② s32_prompt_{novel_type}_{timestamp}.md
     → Opusチャットに「コピペ」するプロンプト

手動実行手順（S32完了後）：
  1. 新しいClaude Opusチャットを開く
  2. s32_prompt を全文コピペして送信
  3. s32_input を添付ファイルとして追加
  4. 「STEP1から開始してください」と送信
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import load_config
from datetime import datetime

OUTPUT_DIR  = Path(__file__).parent.parent / "output" / "s32_check"
S31_DIR     = Path(__file__).parent.parent / "output" / "s31_trim"
VISION_PATH = Path(__file__).parent.parent / "input" / "vision.md"

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


# ============================================================
# vision.md の読み込み（求める作品像）
# ============================================================

def load_vision() -> str:
    """
    input/vision.md を読み込んで返す。
    ファイルが存在しない場合は空文字を返す（WARNログ表示）。
    """
    if not VISION_PATH.exists():
        print(f"  [WARN] vision.md が見つかりません → {VISION_PATH}")
        print(f"         投稿先の「求める作品像」を記載したファイルを配置してください。")
        return ""
    content = VISION_PATH.read_text(encoding="utf-8").strip()
    print(f"  [OK] vision.md 読み込み済み ({len(content)}字)")
    return content


# ============================================================
# S31ファイルの読み込み
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


def load_s31_sections(novel_type: str) -> list[dict]:
    """
    S31出力を読み込んでセクション情報リストを返す。
    探索優先：s31_{novel_type}_{n}_latest.md
           → s31_{novel_type}_{n}_*.md の最新タイムスタンプ
    """
    results = []
    for sec in SECTIONS:
        n, name = sec["id"], sec["name"]
        path = None

        # latest ファイル
        p_latest = S31_DIR / f"s31_{novel_type}_{n}_latest.md"
        # タイムスタンプ付き最新ファイル
        candidates = sorted(S31_DIR.glob(f"s31_{novel_type}_{n}_*.md"))
        p_ts = candidates[-1] if candidates else None

        for candidate in [p_latest, p_ts]:
            if candidate and Path(candidate).exists():
                path = Path(candidate)
                break

        if path is None:
            print(f"  [WARN] Section {n}「{name}」: S31ファイルが見つかりません")
            results.append({"id": n, "name": name, "content": "", "chars": 0})
            continue

        content = _extract_body(path.read_text(encoding="utf-8"))
        chars   = len(content.replace("\n","").replace("\r","").replace(" ",""))
        results.append({"id": n, "name": name, "content": content, "chars": chars})
        print(f"  [OK] Section {n}「{name}」: {chars:,}字  ({path.name})")

    return results


# ============================================================
# ① 統合テキストファイル生成（Opusに添付するファイル）
# ============================================================

def build_input_file(sections: list[dict], novel_type: str, timestamp: str) -> Path:
    """全セクションを1ファイルに統合してOpusへの添付用ファイルを生成"""
    total = sum(s["chars"] for s in sections if s["chars"] > 0)

    lines = [
        f"# 「白の家」全文（S31処理済み）",
        f"生成日時：{timestamp}",
        f"総文字数：{total:,}字",
        f"小説タイプ：{novel_type}",
        "",
        "---",
        "",
    ]

    for s in sections:
        if not s["content"]:
            continue
        lines += [
            f"",
            f"============================================================",
            f"[Section {s['id']}：{s['name']}  {s['chars']:,}字]",
            f"============================================================",
            f"",
            s["content"],
            "",
        ]

    content = "\n".join(lines)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"s32_input_{novel_type}_{timestamp}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================
# ② コピペ用プロンプトファイル生成
# ============================================================

def build_opus_prompt(vision_text: str) -> str:
    """
    vision.md の内容を注入したOpusチャット用プロンプトを返す。
    vision_text が空の場合はデフォルトメッセージを表示。
    """
    if vision_text:
        vision_section = f"""\
### 【前提】投稿先が求める作品像（vision.md より）

以下は投稿先・出版社・コンテストが求める作品像です。
修正案を出す際、この要件に最も合致する案に【推奨】を付けること。
推奨理由は「どの要件に合致するか」を1行で添えること。

```
{vision_text}
```"""
    else:
        vision_section = """\
### 【前提】投稿先の要件
（vision.md が見つからないため、投稿先要件の注入はスキップされました）"""

    return f"""\
# S32 整合性チェック・修正プロンプト（白の家）
## 使い方
1. このプロンプトをそのまま Claude Opus チャットに貼り付ける
2. s32_input ファイルを添付する
3. 「STEP1から開始してください」と送信

---

## プロンプト本文（ここから下をコピー）

---

あなたは「褒めない編集者」として小説「白の家」の整合性チェックを行います。
以下の手順で進めてください。

---

### 【前提】あなたが参照するファイル

**チェック対象の文章（添付ファイル）：**
S31処理済みの全文統合テキスト（Section 0〜8）

**登場人物（記憶として参照）：**
- 朝倉湊（主人公・17歳・施設職員）
- 白川礼（子ども・「先生」と呼ぶ）
- 篠冬子（アナリティカル・最小限の言葉）
- カイ（トリックスター・フェンス外から現れる）
- 御堂（ブレイン・記録の管理者）

---

{vision_section}

---

### 【手順】

**STEP1：整合性チェック**
文章全体を通して読み、🔴🟡🟢の指摘を洗い出す。

```
🔴 致命的な問題（必ず修正が必要）
🟡 要確認（著者の意図次第では問題なし）
🟢 軽微（好みの問題・参考意見）
```

---

**STEP2：設計判断が必要な🔴の特定**
以下のいずれかに該当する🔴を「判断が必要」として抽出する：
- 複数の修正案がある
- 著者の意図が必要
- 削除・統合・書き直しなど複数の方向性がある

---

**STEP3：1問ずつ質問**
判断が必要な🔴に対して、**1問ずつ**質問する。
全問回答が終わるまで最終結果（STEP4）を出力しない。

```
━━━━━━━━━━━━━━━━━━━━
【判断が必要な問題 N/全問数】
問題の概要：〜〜〜〜
選択肢：
  A：〜〜〜〜
  B：〜〜〜〜
  【推奨】C：〜〜〜〜（vision.md の要件に最も合致する案）
  　推奨理由：〜〜（どの要件に合致するか1行で）
どれを選びますか？（A/B/C または自由記述）
━━━━━━━━━━━━━━━━━━━━
```

→ 回答を受け取ったら次の質問へ進む。
→ 全問終了後に「全ての回答を受け取りました。最終結果を出力します。」と宣言してからSTEP4へ。

---

**STEP4：最終整合性チェック結果の出力**

```
## 🔴 致命的（判断済み・修正方針確定）
・問題：
・採用した方針：
・具体的な修正指示：
・投稿先要件との整合：

## 🟡 要確認（意図的なら問題なし）
・箇所：
・問題：
・確認事項：
・【推奨】投稿先要件への改善案：

## 🟢 軽微（好みの問題）
・箇所：
・指摘：

## 【修正ロードマップ】
優先度1（必須）：
優先度2（推奨・投稿先要件向上）：
優先度3（任意）：

## 【固定事実Bible出力】
---bible_short.md---
【固定事実Bible】
作品名：白の家

■ キャラクター
（確定した設定を列挙）

■ 固有名詞・場所
（確定した設定を列挙）

■ 時系列・メカニズム
（確定した設定を列挙）

■ セクション別プロット制約（絶対遵守）
（各セクションで起きること・起きないことを列挙）

■ 絶対禁止事項（全章・全シーン）
（書いてはいけない描写を列挙）
---end---
```

---

### 【注意事項】
- 褒めない。問題点を的確に指摘することに集中する
- STEP3では必ず1問ずつ送信する（まとめて送らない）
- 著者の「こういう意図だった」という説明は尊重する
- 修正指示は「どこを・どのように・なぜ」まで具体的に書く
- 【推奨】は必ずvision.mdの要件との関連理由とセットで表示する

---

ではSTEP1から開始してください。
（s32_input ファイルを添付してから送信してください）
"""


def build_prompt_file(vision_text: str, novel_type: str, timestamp: str) -> Path:
    """Opusチャットへのコピペ用プロンプトファイルを生成"""
    content = build_opus_prompt(vision_text)
    path = OUTPUT_DIR / f"s32_prompt_{novel_type}_{timestamp}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    novel_type = config.get("novel_type", "short")
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")

    print(f"\n[S32] 整合性チェック準備 開始")
    print(f"  小説タイプ : {novel_type}")

    # ── S31ファイル読み込み ─────────────────────────────────
    print("\n  S31ファイル読み込み中...")
    sections = load_s31_sections(novel_type)

    loaded = [s for s in sections if s["chars"] > 0]
    if not loaded:
        print("  [ERROR] S31ファイルが1つも見つかりません。")
        print("          先に S31 を実行してください。")
        return {}

    total_chars = sum(s["chars"] for s in loaded)

    # ── vision.md 読み込み ──────────────────────────────────
    print("\n  vision.md 読み込み中...")
    vision_text = load_vision()

    # ── ① 統合テキストファイル生成 ─────────────────────────
    input_path  = build_input_file(sections, novel_type, timestamp)
    print(f"\n  [OK] 統合テキスト: {input_path.name}  ({total_chars:,}字)")

    # ── ② コピペ用プロンプト生成 ────────────────────────────
    prompt_path = build_prompt_file(vision_text, novel_type, timestamp)
    print(f"  [OK] チェックプロンプト: {prompt_path.name}")

    # ── 手動実行の手順を表示 ────────────────────────────────
    print(f"""
{'=' * 60}
[S32] ファイル準備完了

【次の手順】

  1. Claude Opus の新規チャットを開く

  2. 以下のファイルの内容をコピペする：
     {prompt_path}

  3. 以下のファイルを添付する：
     {input_path}

  4. 「STEP1から開始してください」と送信

  ※ S32はOpusを使うため手動実行です。
{'=' * 60}
""")

    return {
        "input_path":  str(input_path),
        "prompt_path": str(prompt_path),
        "total_chars": total_chars,
        "timestamp":   timestamp,
    }


# ============================================================
# エントリポイント
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"] = args.type
    run(config=_config)
