# -*- coding: utf-8 -*-
"""
S30：セリフ再強化スキル
呼び出し：python run_pipeline.py --skill 30 --type short --section 0
役割：S29統合出力のセリフを1行ずつ前後200字の文脈付きで再生成する。
     S29時点では周囲に豊富な情景・心理描写があるため、
     S26時点より文脈が豊かな状態でセリフを強化できる。

ツール割り当て（新仕様）：
  湊（ドライバー）       → Claude Haiku   ← API自動
  礼（エミアブル）       → GPT-5.5 Think  ← API自動
  冬子（アナリティカル） → Claude Sonnet  ← API自動
  御堂（ブレイン）       → Gemini Pro     ← API自動
  カイ（トリックスター秩序）→ NovelAI     ← 手動処理
  モブ・その他           → Gemini高速     ← 手動処理

目標文字数：
  湊：15〜25字 / 礼：20〜35字 / 冬子：15〜25字
  御堂：25〜40字 / カイ：15〜30字
"""

import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet, call_claude_haiku,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s30_dialogue_enhance"


# ============================================================
# S10キャラクター設計の読み込み
# ============================================================

def _load_s10_char_info(novel_type: str) -> dict:
    """S10出力から各キャラの口癖・口調情報を抽出して返す"""
    base = Path(__file__).parent.parent / "output" / "s10_character"
    pattern = f"s10_{novel_type}_*.md"
    files = sorted(base.glob(pattern), reverse=True)
    if not files:
        # latestファイルを試す
        latest = base / f"s10_character_latest_{novel_type}.md"
        if latest.exists():
            files = [latest]
    if not files:
        return {}

    text = files[0].read_text(encoding="utf-8")

    # キャラ別に口癖セクションを抽出
    char_map = {"蓮": "日暮", "佐和子": "霧島", "遠田": "遠田"}
    result = {}
    for char, search_key in char_map.items():
        # 口癖・動作の癖セクションを探す
        sections = text.split("**口癖・動作の癖：**")
        for i, sec in enumerate(sections[1:], 1):
            lines = sec.strip().split("\n")
            tips = [l.strip("- ").strip() for l in lines
                    if l.strip().startswith("- ") and l.strip()][:3]
            if tips:
                # どのキャラの口癖かを前のテキストから判定
                prev_text = sections[i-1][-200:]
                if search_key in prev_text:
                    result[char] = tips
                    break

    return result


def _build_char_rules(char_name: str, base_rules: str,
                      s10_info: dict) -> str:
    """S10情報をベースルールに追記して返す"""
    tips = s10_info.get(char_name, [])
    if not tips:
        return base_rules
    tips_text = "\n".join(f"  ・{t}" for t in tips)
    return f"{base_rules}\n【S10キャラクター固有の特徴】\n{tips_text}"


# ============================================================
# All ファイル管理
# ============================================================

def _get_all_filepath(novel_type: str) -> Path:
    return OUTPUT_DIR / f"s30_all_{novel_type}.md"


def _update_all_file(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    all_path = _get_all_filepath(novel_type)
    separator = f"\n\n{'='*60}\n[Section {section_idx}：{section_name}]\n{'='*60}\n"
    if all_path.exists():
        existing = all_path.read_text(encoding="utf-8")
        marker = f"[Section {section_idx}："
        if marker in existing:
            cut_pos = existing.find(marker)
            existing = existing[:cut_pos].rstrip()
        all_path.write_text(existing + separator + content, encoding="utf-8")
    else:
        header = f"# S30 全セクション統合（{novel_type})\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context(novel_type: str, current_idx: int, n: int = 2) -> str:
    all_path = _get_all_filepath(novel_type)
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


# ============================================================
# セクション定義
# ============================================================

SECTIONS = {
    "short": [
        {"index": 0, "key": "prologue",    "name": "プロローグ"},
        {"index": 1, "key": "ch01",        "name": "第1章"},
        {"index": 2, "key": "ch02_03",     "name": "第2〜3章"},
        {"index": 3, "key": "ch04_05",     "name": "第4〜5章"},
        {"index": 4, "key": "midpoint",    "name": "ミッドポイント"},
        {"index": 5, "key": "ch06_07",     "name": "第6〜7章"},
        {"index": 6, "key": "turn",        "name": "転"},
        {"index": 7, "key": "ch09_10",     "name": "第9〜10章"},
        {"index": 8, "key": "epilogue",    "name": "エピローグ"},
    ],
}

# ============================================================
# キャラクター設定
# ============================================================

CHAR_CONFIG = {
    "蓮": {
        "ai":     "claude_haiku",
        "style":  "ドライバー",
        "min":    5, "max": 30,
        "rules":  "現代の高校生らしいカジュアル口語。「〜だよ」「〜じゃん」「〜だろ」積極使用。「俺」一人称。感情語なし。以下の確定セリフは一字も変えない：「寒いから」「危ないから」「ここにいて」「れん、いる」「そうだよ、いる」「外、行く？」「帰る場所、ある？」",
    },
    "ハク": {
        "ai":     "gpt55_instinct",
        "style":  "ゴート",
        "min":    1, "max": 8,
        "rules":  "2〜4語の断片。助詞を省く。「れん、いる」「そと」のような最小限の発話。「…」使用可。",
    },
    "佐和子": {
        "ai":     "claude_sonnet",
        "style":  "アナリティカル",
        "min":    10, "max": 50,
        "rules":  "丁寧語・崩れない専門家。感情を表に出さない。情報を最小限に開示。「…」使用可。",
    },
    "遠田": {
        "ai":     "gemini_pro",
        "style":  "ブレイン",
        "min":    2, "max": 20,
        "rules":  "多くて1文。説明・感情表明をしない。事実だけを短く告げる。「…」使用可。",
    },
}

CHAR_CONFIG["モブ・その他"] = {
    "ai":    "gemini_fast",
    "style": "ゴート",
    "min":   3, "max": 20,
    "rules": "自然な日常語。個性不要。場に馴染む短文。",
}

MANUAL_CHARS = []  # 今作は手動処理対象なし

CONTEXT_WINDOW = 200  # 前後何字の文脈を使うか

# ============================================================
# S29ファイルの読み込み
# ============================================================

def load_s29_section(novel_type: str, section_index: int,
                     sections: list) -> tuple:
    """S29統合ファイルから指定セクションの本文を抽出する"""
    import re as _re
    section = sections[section_index]
    base = Path(__file__).parent.parent / "output" / "s29_integrated"

    # 単一統合ファイルを検索
    patterns = [
        f"s29_{novel_type}_integrated_draft_*.md",
        f"s29_short_integrated_draft_*.md",
    ]
    files = []
    for pat in patterns:
        files = sorted(base.glob(pat), reverse=True)
        if files:
            break
    if not files:
        return "", 0

    full_text = files[0].read_text(encoding="utf-8")

    # セクション名で分割して該当部分を抽出
    section_name = section["name"]
    sep = "=" * 60
    # 「セクション名】」形式でも「Section名】」形式でも対応
    pattern_header = _re.compile(
        r"={5,}\n"
        r"(?:【[^】]*" + _re.escape(section_name) + r"[^】]*】|\[Section \d+：" + _re.escape(section_name) + r"\])"
        r"\n={5,}\n",
        _re.MULTILINE
    )
    matches = list(pattern_header.finditer(full_text))
    if not matches:
        # フォールバック：セクション名で単純検索
        idx = full_text.find(section_name)
        if idx == -1:
            return "", 0
        start = full_text.find("\n", idx) + 1
    else:
        match = matches[0]
        start = match.end()

    # 次のセパレータまでを取得
    next_sep = full_text.find(sep, start)
    if next_sep == -1:
        body = full_text[start:].strip()
    else:
        body = full_text[start:next_sep].strip()

    return body, len(body)


# ============================================================
# セリフ抽出・置換
# ============================================================

def extract_dialogues(body: str) -> list:
    """▷キャラ名：「...」形式のセリフを位置情報付きで抽出"""
    pattern = re.compile(r'(▷([^：]+)：「([^」]*)」)')
    results = []
    for m in pattern.finditer(body):
        results.append({
            "full":   m.group(1),   # ▷湊：「...」
            "char":   m.group(2).strip(),
            "line":   m.group(3),   # セリフ本文
            "start":  m.start(),
            "end":    m.end(),
        })
    return results


def get_context(body: str, start: int, end: int, window: int = CONTEXT_WINDOW) -> str:
    """セリフの前後window字の文脈を返す"""
    pre  = body[max(0, start - window):start].strip()
    post = body[end:end + window].strip()
    return pre, post


def build_regen_prompt(char_name: str, cfg: dict, line: str,
                       pre: str, post: str, context_prev: str = "") -> str:
    return f"""以下のセリフを{cfg['style']}スタイルで再生成してください。

{context_prev}
【キャラクター】{char_name}（{cfg['style']}）
【ルール】{cfg['rules']}
【目標文字数】{cfg['min']}〜{cfg['max']}字

【直前の文章】
{pre}

【現在のセリフ（再生成対象）】
▷{char_name}：「{line}」

【直後の文章】
{post}

【出力形式】
セリフ本文のみを出力してください。「」は不要。前置き・解説も不要。
例：わかりました
"""


# ============================================================
# AI呼び出し
# ============================================================

def _call_ai(char_name: str, prompt: str, config: dict) -> str:
    cfg = CHAR_CONFIG.get(char_name)
    if not cfg:
        return ""
    ai = cfg["ai"]

    if ai == "claude_haiku":
        import time
        for attempt in range(3):
            try:
                return call_claude_haiku(prompt)
            except Exception as e:
                if attempt < 2:
                    print(f"      [RETRY] Haiku {attempt+1}/3: {e}")
                    time.sleep(3)
                else:
                    print(f"      [WARN] Haiku失敗 → Sonnetにフォールバック")
                    return call_claude_sonnet(prompt)

    elif ai == "claude_sonnet":
        import time
        for attempt in range(3):
            try:
                return call_claude_sonnet(prompt)
            except Exception as e:
                if attempt < 2:
                    print(f"      [RETRY] Sonnet {attempt+1}/3: {e}")
                    time.sleep(3)
                else:
                    return original if 'original' in dir() else ""

    elif ai == "gpt55_thinking":
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
            from openai_utils import call_openai_thinking
            model  = config.get("openai_model", "gpt-5.5-2026-04-23")
            result = call_openai_thinking(prompt, model=model,
                                          reasoning_effort="high",
                                          max_tokens=1000)
            return result or call_claude_sonnet(prompt)
        except Exception as e:
            print(f"      [WARN] GPT-5.5エラー: {e} → Sonnetにフォールバック")
            return call_claude_sonnet(prompt)

    elif ai == "gemini_pro":
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
            # call_gemini_pro → call_gemini_thinking → call_gemini の順で試行
            from gemini_utils import call_gemini_thinking
            result = call_gemini_thinking(prompt, model="gemini-2.5-pro", config=config)
            return result.strip() if result and result.strip() else call_claude_sonnet(prompt)
        except Exception as e:
            print(f"      [WARN] Gemini Proエラー: {e} → Sonnetにフォールバック")
            return call_claude_sonnet(prompt)

    elif ai == "gemini_fast":
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
            from gemini_utils import call_gemini_thinking
            result = call_gemini_thinking(prompt, model="gemini-2.5-flash", config=config)
            return result.strip() if result and result.strip() else call_claude_sonnet(prompt)
        except Exception as e:
            print(f"      [WARN] Gemini高速エラー: {e} → Sonnetにフォールバック")
            return call_claude_sonnet(prompt)

    return call_claude_sonnet(prompt)


def _validate_result(result: str, cfg: dict, original: str) -> str:
    """生成結果を検証。問題あればoriginalを返す"""
    import re
    if not result or not result.strip():
        return original
    # 「」を除去
    cleaned = result.strip().strip('「」')
    # 二重出力バグ除去：「▷キャラ：「xxx」」→「xxx」
    double = re.search(r'▷[^：]+：「([^」]*)」', cleaned)
    if double:
        cleaned = double.group(1)
    # ▷ が残っていたら元に戻す
    if '▷' in cleaned:
        return original
    # 文字数チェック（目標の3倍を超えたら元に戻す）
    if len(cleaned) > cfg["max"] * 3:
        return original
    return cleaned


# ============================================================
# 手動処理リスト生成
# ============================================================

def generate_manual_list(body: str, section_name: str,
                         dialogues: list) -> str:
    result = f"【S30手動処理リスト：{section_name}】\n\n"
    manual = [d for d in dialogues if d["char"] in MANUAL_CHARS]

    result += "■ 手動処理対象：なし（今作はMANUAL_CHARS空）\n"
    if manual:
        for d in manual:
            pre, post = get_context(body, d["start"], d["end"])
            result += f"  キャラ：{d['char']}\n"
            result += f"  前文脈：{pre[-80:]}\n"
            result += f"  現在：「{d['line']}」\n"
            result += f"  後文脈：{post[:80]}\n\n"
    else:
        result += "  （このセクションに手動処理セリフなし）\n"
    return result


# ============================================================
# メイン処理
# ============================================================

def run(config: dict = None, section_index: int = None) -> dict:
    if config is None:
        config = load_config()

    token      = config["api_keys"]["notion_token"]
    plot_db    = config["notion_dbs"].get("plot_db", "")
    novel_type = config.get("novel_type", "short")
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")
    sections   = SECTIONS.get(novel_type, SECTIONS["short"])

    targets = [section_index] if section_index is not None \
              else list(range(len(sections)))

    print("\n[S30] セリフ再強化スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  API自動: 湊（Haiku）/ 礼（GPT-5.5）/ 冬子（Sonnet）/ 御堂（Gemini Pro）/ モブ（Gemini高速）")
    print(f"  手動処理: カイ（NovelAI）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/8] {section['name']} 処理中...")

        body, body_len = load_s29_section(novel_type, idx, sections)
        if not body:
            print(f"  [SKIP] S29入力ファイルなし")
            continue

        # ── All から前セクション文脈 ───────────────
        n_ctx = int(config.get("context_sections", 2))
        context_prev = _load_context(novel_type, idx, n=n_ctx) if idx > 0 else ""
        if context_prev:
            print(f"    [文脈] 直近{n_ctx}セクションを注入")

        # ── S10キャラ情報読み込み ─────────────────
        s10_info = _load_s10_char_info(novel_type)
        if s10_info:
            print(f"    [S10] キャラ情報注入: {list(s10_info.keys())}")

        # ── セリフ抽出 ────────────────────────────
        dialogues = extract_dialogues(body)
        api_dialogues = [d for d in dialogues
                         if d["char"] in CHAR_CONFIG]
        print(f"  [INFO] セリフ総数: {len(dialogues)}行"
              f"（API対象: {len(api_dialogues)}行）")

        current = body

        # ── 1行ずつ再生成 ─────────────────────────
        offset = 0  # 置換による文字位置ズレ補正
        for i, d in enumerate(dialogues):
            char = d["char"]
            if char not in CHAR_CONFIG:
                continue  # 手動対象はスキップ

            cfg = CHAR_CONFIG[char]
            pre, post = get_context(current,
                                    d["start"] + offset,
                                    d["end"]   + offset)
            # S10の口癖情報をrulesに追記
            enriched_rules = _build_char_rules(char, cfg["rules"], s10_info)
            cfg_enriched = dict(cfg)
            cfg_enriched["rules"] = enriched_rules
            prompt = build_regen_prompt(
                char, cfg_enriched, d["line"], pre, post,
                context_prev=context_prev)

            result_raw = _call_ai(char, prompt, config)
            new_line   = _validate_result(result_raw, cfg, d["line"])

            if new_line != d["line"]:
                old_full = f'▷{char}：「{d["line"]}」'
                new_full = f'▷{char}：「{new_line}」'
                current  = current.replace(old_full, new_full, 1)
                offset  += len(new_full) - len(old_full)

            if (i + 1) % 10 == 0:
                print(f"    {i+1}/{len(dialogues)} 行処理済み...")

        print(f"  完了：{body_len}字 → {len(current)}字"
              f"（{len(current)-body_len:+}字）")

        # ── ファイル保存 ──────────────────────────
        header = (f"# セリフ再強化済み：{section['name']}\n"
                  f"実行日時：{timestamp}\n"
                  f"文字数：{len(current):,}字\n\n---\n\n")
        saved_name = f"s30_{novel_type}_{idx}_{timestamp}.md"
        filepath = OUTPUT_DIR / saved_name
        filepath.write_text(header + current, encoding="utf-8")
        print(f"  [OK] Saved: {saved_name}")

        # ── All ファイル更新 ──────────────────────
        _update_all_file(novel_type, idx, section["name"], current)
        print(f"  [OK] s30_all_{novel_type}.md 更新")

        # ── 手動処理リスト ────────────────────────
        manual_list = generate_manual_list(current, section["name"], dialogues)
        manual_path = OUTPUT_DIR / f"s30_{novel_type}_manual_{idx}_{timestamp}.md"
        manual_path.write_text(manual_list, encoding="utf-8")
        print(f"  [手動リスト] Saved: {manual_path.name}")
        print(f"  話者未特定（▷不明）があれば手動で確認してください")

        # ── Notion保存 ────────────────────────────
        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_セリフ再強化")},
                "スキル":     {"rich_text": txt("S30_セリフ再強化")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select":    {"name": "未使用"}},
            }, "セリフ再強化", current[:2000])

        results[section["key"]] = current

    total = sum(len(v) for v in results.values())
    print(f"\n[S30] 完了 / 合計文字数: {total:,}字")
    print(f"  次のステップ: S31（既視感除去＋文章量調整）")
    print(f"  コマンド例: python run_pipeline.py --skill 31 --type {novel_type}")
    print("=" * 60)

    return {"results": results, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",    default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--section", type=int, default=None)
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"] = args.type
    run(config=_config, section_index=args.section)
