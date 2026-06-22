# -*- coding: utf-8 -*-
"""
S25：リズム・文体調整スキル
呼び出し：python run_pipeline.py --skill 25 --type short --section 0
役割：S24の初版文章のリズム・文体を調整する。
     使用AI：ChatGPT Thinking（GPT-5.5 xhigh）

調整内容：
  ① 文末「〜た。」の単調な連続を解消
  ② 短文・長文の緩急をつける
  ③ 「ため」「ので」等の因果説明を削除
  ④ AI臭（平均的な接続・説明過多）を除去
  ⑤ 文体の一貫性を確保

次ステップ：S26（セリフ強化）
"""



import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s25_rhythm"


# ============================================================
# All ファイル管理（文章の流れ維持）
# ============================================================

def _get_all_filepath_s25(novel_type: str) -> Path:
    return OUTPUT_DIR / f"s25_all_{novel_type}.md"


def _update_all_file_s25(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    all_path = _get_all_filepath_s25(novel_type)
    separator = f"\n\n{'='*60}\n[Section {section_idx}：{section_name}]\n{'='*60}\n"
    if all_path.exists():
        existing = all_path.read_text(encoding="utf-8")
        marker = f"[Section {section_idx}："
        if marker in existing:
            cut_pos = existing.find(marker)
            existing = existing[:cut_pos].rstrip()
        all_path.write_text(existing + separator + content, encoding="utf-8")
    else:
        header = f"# S25 全セクション統合（{novel_type})\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context_s25(novel_type: str, current_idx: int, n: int = 2) -> str:
    all_path = _get_all_filepath_s25(novel_type)
    if not all_path.exists():
        return ""
    text = all_path.read_text(encoding="utf-8")
    parts = text.split("[Section ")
    results = []
    for ti in range(max(0, current_idx - n), current_idx):
        for part in parts[1:]:
            if part.startswith(f"{ti}："):
                results.append(part[-2000:])
                break
    if not results:
        return ""
    return f"【前セクション文脈（直近{n}件）】\n" + "\n---\n".join(results) + "\n"

SECTIONS = {
    "short": [
        {"index": 0, "key": "prologue",  "name": "プロローグ"},
        {"index": 1, "key": "ch1",       "name": "第1章"},
        {"index": 2, "key": "ch2_3",     "name": "第2〜3章"},
        {"index": 3, "key": "ch4_5",     "name": "第4〜5章"},
        {"index": 4, "key": "midpoint",  "name": "ミッドポイント"},
        {"index": 5, "key": "ch6_7",     "name": "第6〜7章"},
        {"index": 6, "key": "turning",   "name": "転"},
        {"index": 7, "key": "ch9_10",    "name": "第9〜10章"},
        {"index": 8, "key": "epilogue",  "name": "エピローグ"},
    ],
    "medium": [
        {"index": 0, "key": "prologue",  "name": "プロローグ"},
        {"index": 1, "key": "ch1_2",     "name": "第1〜2章"},
        {"index": 2, "key": "ch3_6",     "name": "第3〜6章"},
        {"index": 3, "key": "midpoint",  "name": "ミッドポイント"},
        {"index": 4, "key": "ch8_10",    "name": "第8〜10章"},
        {"index": 5, "key": "turning",   "name": "転"},
        {"index": 6, "key": "ch12_14",   "name": "第12〜14章"},
        {"index": 7, "key": "epilogue",  "name": "エピローグ"},
    ],
}

RHYTHM_RULES = """
【リズム・文体調整ルール】

■ 最優先：文末の単調さを解消
  ❌ 悪い例：「〜た。〜た。〜た。〜た。」が3文以上続く
  ✅ 修正法：
    ・体言止めに変える（「音だけが、残った。」）
    ・現在形に変える（「指が、震えている。」）
    ・倒置に変える（「残ったのは、音だけだった。」）
    ・短文を一文に統合する
    ・長文で緩和を入れる

■ 文の緩急設計
  ・緊張場面：短文を連続させてテンポを上げる
  ・緩和場面：長文で息を入れる
  ・余韻場面：体言止め・一語文で終わらせる

■ AI臭の除去
  ❌ 「〜ため」「〜ので」「〜から」の因果説明
  ❌ 「〜ように」の多用
  ❌ 「少し」「わずかに」「かすかに」の連続
  ❌ 同じ動詞の繰り返し（「見た。見た。見た。」）
  → 削除または別の表現に置き換える

■ 絶対に変えてはいけないもの
  ✅ 確定済みの台詞（一字も変えない）
  ✅ キャラクターの一人称・口調
  ✅ 固有名詞・設定の固有情報
  ✅ 余白（書かない設計になっている場面）
  ✅ 感情を直接書いていない設計（変更禁止）
  ✅ 登場人物の呼称・代名詞（「彼」「彼女」「碧」「柚」等を別の名前に置き換えない）
  ✅ 特にプロローグ：主人公を「彼」と呼ぶ意図的な匿名設計を維持すること
"""


def load_s24_section(novel_type: str, section_index: int,
                     sections: list) -> tuple:
    """S24の最新ファイルを読み込む"""
    s24_dir = Path(__file__).parent.parent / "output" / "s24_draft"
    section = sections[section_index]

    # インデックス番号で探す（新命名規則）
    files = sorted(
        s24_dir.glob(f"s24_{novel_type}_{section['index']}_*.md"),
        reverse=True
    )
    # 旧命名規則（key名）でも探す
    if not files:
        files = sorted(
            s24_dir.glob(f"s24_{novel_type}_{section['key']}_*.md"),
            reverse=True
        )

    if not files:
        print(f"  [WARN] S24ファイルが見つかりません: section {section['index']}")
        return "", 0

    text = files[0].read_text(encoding="utf-8")
    # ヘッダーを除いた本文のみ抽出
    if "---" in text:
        body = text.split("---", 1)[-1].strip()
    else:
        body = text

    print(f"  [INFO] S24読み込み: {files[0].name}（{len(body):,}字）")
    return body, len(body)


def build_prompt(section_name: str, body: str, cfg: dict = None) -> str:
    cfg = cfg or {}
    # 登録済みキャラ名を読み込んで保護リストを生成
    from pathlib import Path as _P
    _names_path = _P(__file__).parent.parent / "used_names.json"
    import json as _json
    _names = []
    try:
        _data = _json.loads(_names_path.read_text(encoding="utf-8"))
        # {names:[...]} 形式と [...] 形式の両方に対応
        _names = _data.get("names", _data) if isinstance(_data, dict) else _data
    except Exception:
        pass
    # 登録名がなくてもconfig内のcharacterから取得できる場合はそちらを使う
    if not _names:
        _protagonist = cfg.get("protagonist", "")
        if _protagonist:
            _names = [_protagonist]
    _name_guard = f"【登録済みキャラ名（変更禁止）】{chr(32).join(_names)}" if _names else "【注意】登場人物の呼称（彼・彼女・名前）は元文章のまま維持すること"

    return f"""あなたはこの小説の「リズム・文体調整者」です。
{cfg.get("tone_rule", "")}
{_name_guard}
以下の文章のリズムと文体を調整してください。

{RHYTHM_RULES}

【重要】
・内容（何が起きるか）は一切変更しない
・感情描写の方針（直接書かない）は維持する
・文字数は元の±10%以内に収める
・前置きや説明は不要。調整済み文章のみ出力する

【調整対象：{section_name}】
{body}

では「{section_name}」のリズム・文体調整後の文章を出力してください。
"""


def _call_rhythm_ai(prompt: str, config: dict, body_len: int) -> str:
    """リズム調整AI：GPT-5.5 xhigh優先、フォールバックあり"""
    writing_ai = config.get("writing_ai", "openai")

    if writing_ai == "openai":
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
            from openai_utils import call_openai_thinking
            model  = config.get("openai_model",    "o3")
            effort = config.get("reasoning_effort", "high")
            max_tok = max(8000, body_len * 4)
            print(f"    使用AI: OpenAI {model}（reasoning={effort} / max_tokens={max_tok:,}）")
            result = call_openai_thinking(
                prompt, model=model,
                reasoning_effort=effort,
                max_tokens=max_tok
            )
            if result and len(result.strip()) > 100:
                return result
            print("    [WARN] 空レスポンス → Claude Sonnetにフォールバック")
        except (ImportError, ValueError, RuntimeError) as e:
            print(f"    [WARN] {e} → Claude Sonnetにフォールバック")

    print("    使用AI: Claude Sonnet")
    return call_claude_sonnet(prompt)


def run(config: dict = None, section_index: int = None) -> dict:
    if config is None:
        config = load_config()

    token       = config["api_keys"]["notion_token"]
    plot_db     = config["notion_dbs"].get("plot_db", "")
    novel_type  = config.get("novel_type", "short")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
    sections    = SECTIONS.get(novel_type, SECTIONS["short"])

    if section_index is None:
        targets = list(range(len(sections)))
    else:
        targets = [section_index]

    print("\n[S25] リズム・文体調整スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  対象: {[sections[i]['name'] for i in targets]}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/8] {section['name']} 調整中...")

        body, body_len = load_s24_section(novel_type, idx, sections)
        if not body:
            print(f"  [SKIP] S24ファイルなし")
            continue

        prompt = build_prompt(section["name"], body, config)
        result = _call_rhythm_ai(prompt, config, body_len)

        if not result or len(result.strip()) < 100:
            print(f"  [WARN] 調整結果が空。元文章を保持。")
            result = body

        results[section["key"]] = result
        char_count = len(result)
        diff = char_count - body_len
        print(f"  調整前: {body_len:,}字 → 調整後: {char_count:,}字（{diff:+,}字）")

        # ファイル保存（命名規則：s25_short_0_YYYYMMDD.md）
        filepath = OUTPUT_DIR / f"s25_{novel_type}_{section['index']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# リズム調整済み：{section['name']}\n"
                    f"実行日時：{timestamp}\n"
                    f"文字数：{char_count:,}字（元：{body_len:,}字）\n\n---\n\n{result}")
        print(f"  [OK] Saved: {filepath.name}")

        # ── All ファイル更新 ──────────────────────
        _update_all_file_s25(novel_type, idx, section["name"], result)
        print(f"  [OK] s25_all_{novel_type}.md 更新")

        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_リズム調整")},
                "スキル":     {"rich_text": txt("S25_リズム文体調整")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select": {"name": "未使用"}},
            }, f"リズム調整：{section['name']}", result)

    total = sum(len(v) for v in results.values())
    print(f"\n[S25] 完了 / 合計文字数: {total:,}字")
    print("  次のステップ: S26（セリフ強化）")
    print(f"  コマンド例: python run_pipeline.py --skill 26 --type {novel_type} --section 0")

    return {"result": results, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",    default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--section", type=int, default=None)
    parser.add_argument("--writing-ai", default="openai",
                        choices=["openai", "claude"])
    parser.add_argument("--reasoning-effort", default="high",
                        choices=["none", "low", "medium", "high", "xhigh"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"]       = args.type
    _config["writing_ai"]       = args.writing_ai
    _config["reasoning_effort"] = args.reasoning_effort
    run(config=_config, section_index=args.section)
