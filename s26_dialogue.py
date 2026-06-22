# -*- coding: utf-8 -*-
"""
S26：セリフ強化スキル（キャラ別）
呼び出し：python run_pipeline.py --skill 26 --type short --section 0

キャラ別AIツール割り当て：
  湊（ドライバー）      → Claude Haiku（ドライバー）        ← API自動
  礼（エミアブル）      → GPT-5.5 Thinking（エミアブル）   ← API自動
  冬子（アナリティカル）→ Claude Sonnet（アナリティカル）  ← API自動
  御堂（ブレイン）      → Gemini Pro（ブレイン）           ← API自動
  カイ                → NovelAI（トリックスター秩序）      ← 手動処理
  モブ・その他         → Gemini高速（ゴート）             ← 手動処理

次ステップ：S27（情景描写強化）
"""



import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet, call_claude_haiku,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s26_dialogue"


# ============================================================
# S10キャラクター設計の読み込み
# ============================================================

def _load_s10_char_info(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output" / "s10_character"
    files = sorted(base.glob(f"s10_{novel_type}_*.md"), reverse=True)
    if not files:
        latest = base / f"s10_character_latest_{novel_type}.md"
        if latest.exists():
            files = [latest]
    if not files:
        return {}
    text = files[0].read_text(encoding="utf-8")
    char_map = {"碧": "朝倉", "柚": "水瀬", "久我": "久我", "静": "榛名", "中根": "中根"}
    result = {}
    for char, key in char_map.items():
        sections = text.split("**口癖・動作の癖：**")
        for i, sec in enumerate(sections[1:], 1):
            tips = [l.strip("- ").strip() for l in sec.strip().split("\n")
                    if l.strip().startswith("- ")][:3]
            if tips and key in sections[i-1][-200:]:
                result[char] = tips
                break
    return result


# ============================================================
# All ファイル管理（文章の流れ維持）
# ============================================================

ALL_FILE_SKILL = "s26"

def _get_all_filepath(novel_type: str) -> Path:
    """S26_All ファイルのパスを返す"""
    return OUTPUT_DIR / f"s26_all_{novel_type}.md"


def _update_all_file(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    """All ファイルにセクションを追記（既存の同セクションは上書き）"""
    all_path = _get_all_filepath(novel_type)
    separator = f"\n\n{'='*60}\n【Section {section_idx}：{section_name}】\n{'='*60}\n"

    if all_path.exists():
        existing = all_path.read_text(encoding="utf-8")
        # 同セクションが既にあれば除去して再追記
        marker = f"【Section {section_idx}："
        if marker in existing:
            # そのセクション以降を削除
            cut_pos = existing.find(separator.strip().split("\n")[0])
            if cut_pos == -1:
                cut_pos = existing.find(marker)
            existing = existing[:cut_pos].rstrip()
        all_path.write_text(existing + separator + content, encoding="utf-8")
    else:
        header = f"# S26 全セクション統合（{novel_type}）\n生成日時：随時更新\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context_from_all(novel_type: str, current_section_idx: int,
                           n: int = 2) -> str:
    """All ファイルから直近 n セクションのテキストを返す"""
    all_path = _get_all_filepath(novel_type)
    if not all_path.exists():
        return ""
    text = all_path.read_text(encoding="utf-8")

    # セクション境界でsplit
    import re
    parts = re.split(r"={60}\n\[Section \d+：", text)
    # 対象インデックス範囲：current より前の n セクション
    target_indices = list(range(max(0, current_section_idx - n), current_section_idx))
    if not target_indices:
        return ""

    results = []
    for part in parts[1:]:  # parts[0]はヘッダー
        for ti in target_indices:
            if part.startswith(str(ti) + "：") or f"Section {ti}：" in part[:20]:
                # 末尾2000字まで
                results.append(part[-2000:])
                break

    if not results:
        return ""
    context = "\n---\n".join(results)
    return f"【前のセクションの文章（文脈参照用・直近{n}セクション）】\n{context}\n"


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
}

# ============================================================
# キャラクター別セリフ強化プロンプト定義
# ============================================================

CHAR_PROMPTS = {
    "蓮": {
        "ai":    "claude_haiku",
        "style": "ドライバー",
        "length": "1〜30字",
        "desc":  "16歳男子高校生。感情を抑えつつ行動と事実で語る。今風のカジュアル口語。「俺」一人称。",
        "rules": [
            "1〜30字以内で言い切る",
            "現代の高校生らしいカジュアル口語を使う",
            "「〜だよ」「〜じゃん」「〜だろ」「〜ってこと？」「〜してよ」「〜なんだけど」を積極的に使う",
            "です・ます調は使わない（佐和子への詰問も崩した語調で）",
            "「俺」一人称を維持",
            "感情を言語化しない。行動・事実・問いのみ",
            "「…」「！」「？」を感情表現として積極的に使ってよい",
            "前後のセリフと自然にかみ合っているか確認する",
        ],
        "example_bad":  "「ハクのことを心配していたので、外に出さないようにしていました」",
        "example_good": "「待ってよ」「どこ行くの」「靴ないじゃん、無理だって」「…わかった」「鍵、かけてたんだろ！」",
    },
    "ハク": {
        "ai":    "gpt55_instinct",
        "style": "ゴート",
        "length": "1〜8字",
        "desc":  "13歳相当・中性。言語が限定的。2〜4語の断片的な発話。助詞を省く。素直・純粋・無垢。",
        "rules": [
            "8字以内・2〜4語が上限",
            "助詞を省いてよい（「れん、いる」「そと、あかるい」）",
            "感情・理由を言語化しない。状態と要求のみ",
            "同じ言葉の反復を恐れない",
            "「…」は使ってよい（沈黙・迷いを示す）",
            "「！」は基本使わない（感情爆発は体の動きで示す）",
            "前後の会話に素直に反応する（かみ合いを大切に）",
        ],
        "example_bad":  "「蓮さん、外に出てみたいんです。帰りたい気持ちがあります」",
        "example_good": "「そと」「れん、いる」「つめたい」「いやだ」「…れん」「いく？」",
    },
    "佐和子": {
        "ai":    "claude_sonnet",
        "style": "アナリティカル",
        "length": "1〜50字",
        "desc":  "42歳・NPO代表。分析型。丁寧で温かいが崩れない。情報を小出しにする専門家。",
        "rules": [
            "1〜50字で丁寧に答える",
            "です・ます調を維持（温かみのある専門家語）",
            "感情を表に出さない・怒らない・謝らない",
            "蓮の問いに対して正面から答えるが全部は言わない",
            "「〜です」「〜でしょうか」「〜があります」を使う",
            "「…」は使ってよい（言葉を選ぶ間）",
            "前後の会話の流れを受けて応答する（かみ合いを大切に）",
        ],
        "example_bad":  "「そんなこと！ハクのためを思ってやったんです！誤解しないでください！」",
        "example_good": "「外は、ハクさんには難しいんです」「…記録を見てください」「あなたは違うと言えますか」",
    },
    "遠田": {
        "ai":    "gemini_pro",
        "style": "ブレイン",
        "length": "1〜20字",
        "desc":  "38歳・寡黙な知性型。説明せず示唆するだけ。行動で語る。多くて1文。",
        "rules": [
            "20字以内・多くて1文",
            "説明・感情表明・弁明をしない",
            "事実だけを短く告げる。または沈黙",
            "示唆するだけで解説しない（ブレイン型の核心）",
            "「…」は使ってよい（沈黙・間）",
            "「！」「？」は原則使わない（感情を表に出さない）",
            "前後の会話の流れの中で最小限の言葉が最大の重さを持つよう設計する",
        ],
        "example_bad":  "「私はずっとハクが帰れる日を待っていました。本当に申し訳ありませんでした」",
        "example_good": "「これを」「待っています」「…よかった」「それでいいと思います」",
    },
}


# 手動処理対象（今作は手動処理対象なし）
MANUAL_CHARS = {}

# ============================================================
# AI呼び出し関数
# ============================================================

def _call_claude_sonnet_dialogue(prompt: str) -> str:
    return call_claude_sonnet(prompt)


def _call_claude_haiku_dialogue(prompt: str) -> str:
    return call_claude_haiku(prompt)


def _call_gpt55_dialogue(prompt: str, config: dict, body_len: int) -> str:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from openai_utils import call_openai_thinking
        model  = config.get("openai_model", "gpt-5.5-2026-04-23")
        effort = config.get("reasoning_effort", "high")
        max_tok = max(8000, body_len * 4)
        result = call_openai_thinking(
            prompt, model=model,
            reasoning_effort=effort,
            max_tokens=max_tok
        )
        if result and len(result.strip()) > 50:
            return result
        print("    [WARN] GPT-5.5空レスポンス → Claude Sonnetにフォールバック")
    except Exception as e:
        print(f"    [WARN] GPT-5.5エラー: {e} → Claude Sonnetにフォールバック")
    return call_claude_sonnet(prompt)


def _call_gemini_dialogue(prompt: str, config: dict, body_len: int = 2000) -> str:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from gemini_utils import call_gemini_thinking
        max_tok = max(8000, body_len * 4)
        result = call_gemini_thinking(prompt, max_tokens=max_tok, config=config)
        if result and len(result.strip()) > max(50, body_len * 0.3):
            return result
        if result:
            print(f"    [WARN] Gemini出力が短すぎます（{len(result)}字/入力{body_len}字）→ フォールバック")
        else:
            print("    [WARN] Gemini空レスポンス → Claude Sonnetにフォールバック")
    except Exception as e:
        print(f"    [WARN] Geminiエラー: {e} → Claude Sonnetにフォールバック")
    return call_claude_sonnet(prompt)


# ============================================================
# プロンプト構築
# ============================================================

def _call_gemini_fast_dialogue(prompt: str, config: dict) -> str:
    """Gemini高速（ゴート）でモブセリフを強化"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from gemini_utils import call_gemini_flash
        result = call_gemini_flash(prompt, config=config)
        if result and len(result.strip()) > 5:
            return result.strip()
    except Exception as e:
        print(f"      [WARN] Gemini高速エラー: {e} → Sonnetにフォールバック")
    return call_claude_sonnet(prompt)


def _enrich_char_info(char_name: str, char_info: dict,
                     s10_info: dict) -> dict:
    """S10の口癖情報をchar_infoのdescに追記して返す"""
    tips = s10_info.get(char_name, [])
    if not tips:
        return char_info
    enriched = dict(char_info)
    tips_text = " / ".join(tips)
    enriched["desc"] = f"{char_info['desc']} 【S10固有】{tips_text}"
    return enriched


def build_dialogue_prompt(char_name: str, char_info: dict,
                          section_name: str, body: str,
                          context_prev: str = "",
                          config: dict = None) -> str:
    if config is None: config = {}
    rules_text = "\n".join(f"  ・{r}" for r in char_info["rules"])
    # キャラ名保護（viewpoint_ruleは注入しない・別プロジェクト設定混入防止）
    from pathlib import Path as _P
    import json as _json
    _names_path = _P(__file__).parent.parent / "used_names.json"
    _names = []
    try:
        _data = _json.loads(_names_path.read_text(encoding="utf-8"))
        _names = _data.get("names", _data) if isinstance(_data, dict) else _data
    except Exception:
        pass
    _name_guard = f"【登録済みキャラ名（変更禁止）】{' / '.join(_names)}" if _names else "【注意】登場人物の呼称は元文章のまま維持すること"

    return f"""あなたはこの小説の「{char_name}のセリフ専門調整者」です。
{config.get("tone_rule", "")}
{_name_guard}
以下の文章の中から「{char_name}」のセリフのみを強化してください。

【{char_name}のセリフスタイル：{char_info['style']}】
{char_info['desc']}

【強化ルール】
{rules_text}

【良い例】{char_info.get('example_good', '')}

【絶対に変えてはいけないもの】
・{char_name}以外のキャラのセリフ（一字も変えない）
・地の文・描写（一字も変えない）
・{char_name}のセリフでも、意味・情報量は変えない
・確定済みの重要セリフは変えない
・セリフが前後の文脈と自然にかみ合っているか確認する（一方通行でなく会話として成立させる）
・感情は「…」「！」「？」で示してよい（説明するより記号で伝える）
・生き生きとした声を持つ生き物として、そのキャラクターが実際に発声している言葉を書く

【重要】
出力は文章全体を出力してください。
{char_name}のセリフ部分のみ強化し、他は全て元のまま出力します。
前置きや説明は不要。文章のみ出力。

{context_prev}【対象文章：{section_name}】
{body}
"""


# ============================================================
# 手動処理リスト生成
# ============================================================


DIALOGUE_SPLIT_THRESHOLD = 10000  # この文字数を超えたら分割処理
DIALOGUE_MAX_CHUNK = 8000        # 各AIへの最大入力字数


def _split_dialogue_chunks(body: str, max_size: int = DIALOGUE_MAX_CHUNK) -> list:
    """テキストをmax_size字以下のチャンクに分割"""
    if len(body) <= max_size:
        return [body]
    chunks = []
    remaining = body
    while len(remaining) > max_size:
        split_pos = remaining.rfind("\n\n", 0, max_size)
        if split_pos == -1:
            split_pos = remaining.rfind("\n", 0, max_size)
        if split_pos == -1:
            split_pos = max_size
        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _apply_dialogue_pass_chunked(call_fn, prompt_fn, section_name: str,
                                  body: str, config: dict) -> str:
    """テキストを3,000字単位チャンクに分割してセリフ強化し結合する"""
    chunks = _split_dialogue_chunks(body)
    print(f"      → {len(chunks)}チャンク: {[len(c) for c in chunks]}字")
    results = []
    for i, chunk in enumerate(chunks):
        chunk_name = f"{section_name}（{i+1}/{len(chunks)}）"
        prompt = prompt_fn(chunk_name, chunk, config)
        result = call_fn(prompt)
        if result and len(result.strip()) > max(100, len(chunk) * 0.8):
            results.append(result)
        else:
            print(f"      [WARN] チャンク{i+1}：切れ検出 → 元文章を維持")
            results.append(chunk)
    return "\n\n".join(results)

LABEL_PROMPT_TEMPLATE = """以下の小説文章を読み、各台詞（「」で囲まれた部分）の直前に
話者名をラベルとして追加してください。

【ラベル形式】
台詞の直前の行に「▷キャラ名：」を追加する。
例（今作の登場人物）：
  ▷蓮：「どこ行くの」
  ▷ハク：「そと」
  ▷佐和子：「外は、ハクさんには難しいんです」
  ▷遠田：「これを」
  ▷不明：（話者が特定できない場合）

【ルール】
・地の文は一切変えない
・台詞の内容も一切変えない
・話者が文脈から明確に判断できる場合のみラベルを付ける
・地の文の中に埋め込まれた台詞（「〜と言った」形式）もラベルを付ける
・話者が不明な場合は「▷不明：」とする
・前置きや説明は不要。ラベル付き文章のみ出力する
・実際に文章に存在しない台詞を新たに作成・追加してはいけない
・「…」だけの台詞や内容のない台詞ラベルを挿入してはいけない
・台詞が一切存在しないセクションには、ラベルを一切付けない

【対象文章：{section_name}】
{body}
"""

LABEL_CHUNK_SIZE = 8000  # この文字数を超えたら分割処理（DIALOGUE_MAX_CHUNKと同期）

def _label_single_chunk(chunk: str, section_name: str) -> str:
    """1チャンクにラベルを付与する"""
    prompt = LABEL_PROMPT_TEMPLATE.format(section_name=section_name, body=chunk)
    result = call_claude_sonnet(prompt)
    if result and len(result.strip()) > max(100, len(chunk) * 0.4):
        return result
    print(f"    [WARN] ラベル付与：出力が短すぎます → 元文章を維持")
    return chunk

def add_speaker_labels(body: str, section_name: str) -> str:
    """全セリフの冒頭に話者名ラベルを付与する（Claude Sonnet使用）
    3,000字超は前後半に分割して処理する"""
    if len(body) <= LABEL_CHUNK_SIZE:
        return _label_single_chunk(body, section_name)

    # 分割処理
    mid = len(body) // 2
    split_pos = body.find("\n\n", mid)
    if split_pos == -1:
        split_pos = body.find("\n", mid)
    if split_pos == -1:
        split_pos = mid

    first_half  = body[:split_pos].strip()
    second_half = body[split_pos:].strip()
    print(f"    → ラベル分割: 前半{len(first_half):,}字 / 後半{len(second_half):,}字")

    result_first  = _label_single_chunk(first_half,  section_name + "（前半）")
    result_second = _label_single_chunk(second_half, section_name + "（後半）")
    return result_first + "\n\n" + result_second


def generate_manual_list(body: str, section_name: str) -> str:
    """今作は手動処理対象キャラなし（MANUAL_CHARS={}）。
    未特定話者（▷不明）のみ抽出してレポートする。"""
    import re as _re
    lines = body.split("\n")
    unknown_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = _re.match(r'^▷不明：(「.+」)$', stripped)
        if m:
            unknown_lines.append(f"  行{i+1}: {stripped}")

    result = f"\n{'='*50}\n"
    result += f"【手動処理リスト：{section_name}】\n"
    result += f"{'='*50}\n\n"
    result += "■ 手動処理対象キャラ：なし（今作は手動処理不要）\n\n"

    if unknown_lines:
        result += "■ 話者未特定セリフ（要確認）\n"
        result += "\n".join(unknown_lines) + "\n"
    else:
        result += "■ 話者未特定セリフ：なし\n"

    return result


# ============================================================
# S25出力の読み込み
# ============================================================

def load_s25_section(novel_type: str, section_index: int,
                     sections: list) -> tuple:
    s25_dir = Path(__file__).parent.parent / "output" / "s25_rhythm"
    section = sections[section_index]

    files = sorted(
        s25_dir.glob(f"s25_{novel_type}_{section['index']}_*.md"),
        reverse=True
    )
    if not files:
        # S24にフォールバック
        s24_dir = Path(__file__).parent.parent / "output" / "s24_draft"
        files = sorted(
            s24_dir.glob(f"s24_{novel_type}_{section['index']}_*.md"),
            reverse=True
        )
        if files:
            print(f"  [INFO] S25なし → S24を使用: {files[0].name}")

    if not files:
        return "", 0

    text = files[0].read_text(encoding="utf-8")
    body = text.split("---", 1)[-1].strip() if "---" in text else text
    print(f"  [INFO] 入力: {files[0].name}（{len(body):,}字）")
    return body, len(body)


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None, section_index: int = None) -> dict:
    if config is None:
        config = load_config()

    token      = config["api_keys"]["notion_token"]
    plot_db    = config["notion_dbs"].get("plot_db", "")
    novel_type = config.get("novel_type", "short")
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")
    sections   = SECTIONS.get(novel_type, SECTIONS["short"])

    if section_index is None:
        targets = list(range(len(sections)))
    else:
        targets = [section_index]

    print("\n[S26] セリフ強化スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  API自動処理: 蓮（Haiku）/ ハク（GPT-5.5 Instinct）/ 佐和子（Sonnet）/ 遠田（Gemini Pro）")
    print("  手動処理: なし（今作はMANUAL_CHARS空）")

    s10_info = _load_s10_char_info(novel_type)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    manual_all = ""

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/8] {section['name']} 処理中...")

        body, body_len = load_s25_section(novel_type, idx, sections)
        if not body:
            print(f"  [SKIP] 入力ファイルなし")
            continue

        # ── 前セクションの文脈を読み込み ────────────
        n_ctx = int(config.get("context_sections", 2))
        context_prev = _load_context_from_all(novel_type, idx, n=n_ctx) if idx > 0 else ""
        if context_prev:
            print(f"    [文脈] 直近{n_ctx}セクションを注入")

        current = body

        # ── セリフ存在チェック（「」がゼロなら強化パスをスキップ・保存は通す） ──
        import re as _re_check
        dialogue_count = len(_re_check.findall(r'「[^」]+」', current))
        skip_ai = (dialogue_count == 0)
        if skip_ai:
            print(f"    [SKIP] セリフなし（「」= 0件）→ 強化パスをスキップ（保存は実施）")

        # ── AIセリフ強化パス（セリフなしセクションはスキップ） ──
        if not skip_ai:
            # 蓮（Claude Haiku・ドライバー）
            print(f"    [蓮] Claude Haiku（ドライバー）...")
            prompt_ren = build_dialogue_prompt("蓮", _enrich_char_info("蓮", CHAR_PROMPTS["蓮"], s10_info), section["name"], current, config)
            result = _call_claude_haiku_dialogue(prompt_ren)
            if result and len(result.strip()) > max(100, len(current) * 0.8):
                current = result
            else:
                print(f"    [WARN] 蓮：切れ検出 → スキップ")

            # ハク（GPT-5.5 Instinct・ゴート）
            print(f"    [ハク] GPT-5.5 Instinct（ゴート）...")
            prompt_haku = build_dialogue_prompt("ハク", _enrich_char_info("ハク", CHAR_PROMPTS["ハク"], s10_info), section["name"], current, config)
            result = _call_gpt55_dialogue(prompt_haku, config, body_len)
            if result and len(result.strip()) > 100:
                current = result
            else:
                print(f"    [WARN] ハク：空レスポンス → スキップ")

            # 佐和子（Claude Sonnet・アナリティカル）
            print(f"    [佐和子] Claude Sonnet（アナリティカル）...")
            prompt_sawako = build_dialogue_prompt("佐和子", _enrich_char_info("佐和子", CHAR_PROMPTS["佐和子"], s10_info), section["name"], current, config)
            result = _call_claude_sonnet_dialogue(prompt_sawako)
            if result and len(result.strip()) > max(100, len(current) * 0.8):
                current = result
            else:
                print(f"    [WARN] 佐和子：切れ検出 → スキップ")

            # 遠田（Gemini Pro・ブレイン）
            print(f"    [遠田] Gemini Pro（ブレイン）...")
            prompt_toda = build_dialogue_prompt("遠田", _enrich_char_info("遠田", CHAR_PROMPTS["遠田"], s10_info), section["name"], current, config)
            result = _call_gemini_dialogue(prompt_toda, config, body_len=len(current))
            if result and len(result.strip()) > max(100, len(current) * 0.8):
                current = result
            else:
                print(f"    [WARN] 遠田：切れ検出 → スキップ")

            # 話者ラベル付与
            print(f"    [ラベル] 話者名付与中（Claude Sonnet）...")
            current = add_speaker_labels(current, section["name"])

        # ── 手動処理リスト生成 ────────────────────────
        manual = generate_manual_list(current, section["name"])
        manual_all += manual

        results[section["key"]] = current
        char_count = len(current)
        print(f"  完了：{body_len:,}字 → {char_count:,}字（{char_count - body_len:+,}字）")

        # ファイル保存
        filepath = OUTPUT_DIR / f"s26_{novel_type}_{section['index']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# セリフ強化済み：{section['name']}\n"
                    f"実行日時：{timestamp}\n"
                    f"文字数：{char_count:,}字\n\n---\n\n{current}")
        print(f"  [OK] Saved: {filepath.name}")

        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_セリフ強化")},
                "スキル":     {"rich_text": txt("S26_セリフ強化")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select": {"name": "未使用"}},
            }, f"セリフ強化：{section['name']}", current)

    # 手動処理リストをファイル保存
    if manual_all:
        manual_path = OUTPUT_DIR / f"s26_{novel_type}_manual_list_{section['index']}_{timestamp}.md"
        with open(manual_path, "w", encoding="utf-8") as f:
            f.write(f"# 手動処理リスト（S26セリフ強化）\n実行日時：{timestamp}\n\n{manual_all}")
        print(f"\n  [手動処理リスト] Saved: {manual_path.name}")
        print("  話者未特定（▷不明）があれば手動で確認してください")

    total = sum(len(v) for v in results.values())
    print(f"\n[S26] 完了 / 合計文字数: {total:,}字")
    print("  次のステップ: S27（情景描写強化）")
    print(f"  コマンド例: python run_pipeline.py --skill 27 --type {novel_type} --section 0")

    return {"result": results, "timestamp": timestamp}


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
