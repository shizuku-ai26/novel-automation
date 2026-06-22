# -*- coding: utf-8 -*-
"""
S28：モノローグ強化スキル（6種）
呼び出し：python run_pipeline.py --skill 28 --type short --section 0

config.yaml の novel_viewpoint で処理モードを切り替え：
  novel_viewpoint: "third_person"  → 全体文章（Sonnet）+ 比喩マーカーのみ
  novel_viewpoint: "first_person"  → 全体文章 + キャラ個別パスを全実行

モノローグ割り当て（一人称モード時）：
  全体文章    → Claude Sonnet（固定・API）
  比喩表現   → Sudowrite（固定・手動）

重要思想：
  モノローグは「登場人物が感じていること」を
  内的独白として表現するが、多用するとAI臭になる。
  最小限・最高密度で機能させる。

次ステップ：S29（整合性チェック）
"""



import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet, call_claude_haiku,
    notion_create_page_long, txt
)
try:
    from skills.za_emotion_data import ZA_EMOTIONS
except ImportError:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from za_emotion_data import ZA_EMOTIONS
    except ImportError:
        ZA_EMOTIONS = {}

from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s28_monologue"

# ============================================================
# All ファイル管理（文章の流れ維持）
# ============================================================

def _get_all_filepath_s28(novel_type: str) -> Path:
    return OUTPUT_DIR / f"s28_all_{novel_type}.md"


def _update_all_file_s28(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    all_path = _get_all_filepath_s28(novel_type)
    _sep = "=" * 60
    separator = f"\n\n{_sep}\n[Section {section_idx}：{section_name}]\n{_sep}\n"
    if all_path.exists():
        existing = all_path.read_text(encoding="utf-8")
        marker = f"[Section {section_idx}："
        if marker in existing:
            cut_pos = existing.find(f"[Section {section_idx}：")
            existing = existing[:cut_pos].rstrip()
        all_path.write_text(existing + separator + content, encoding="utf-8")
    else:
        header = f"# S28 全セクション統合（{novel_type})\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context_s28(novel_type: str, current_idx: int, n: int = 2) -> str:
    all_path = _get_all_filepath_s28(novel_type)
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
}

# ============================================================
# モノローグ強化プロンプト定義
# ============================================================

# 三人称限定視点のため、全体文章パスのみ使用
# 個別キャラのモノローグパスは不要（内面は地の文の身体描写で表現）
MONO_PROMPTS = {
    "overall": {
        "label": "全体文章モノローグ",
        "ai":    "claude_sonnet",
        "desc":  "地の文全体のモノローグ的な質感を整える。"
                 "三人称視点を維持しながら主人公の内面が滲む文章に調整。",
        "rules": [
            "三人称視点を崩さない（「碧は思った」より「胸の下が沈んだ」）",
            "内的独白は1シーンに1〜2文まで",
            "感情語禁止（悲しい・怖い・嬉しい等）",
            "身体描写・行動描写で内面を示す",
            "既存の余白設計（【★五感】等）を維持",
            "文字数は元の±10%以内",
        ],
    },
}

# 手動処理対象（三人称視点のため比喩表現のみ）
MANUAL_MONO = {
    "比喩表現": {
        "tool":  "Sudowrite",
        "desc":  "詩的・映像的な比喩表現を強化。特にプロローグ・エピローグ・転。",
        "target": ["プロローグ", "エピローグ", "転"],
    },
}


# ============================================================
# API呼び出し
# ============================================================

def _call_gpt55(prompt: str, config: dict,
                effort: str = "medium", body_len: int = 2000) -> str:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from openai_utils import call_openai_thinking
        model   = config.get("openai_model", "gpt-5.5-2026-04-23")
        max_tok = max(8000, body_len * 4)
        result  = call_openai_thinking(
            prompt, model=model,
            reasoning_effort=effort,
            max_tokens=max_tok
        )
        if result and len(result.strip()) > 100:
            return result
        print(f"    [WARN] GPT-5.5空レスポンス → Claude Sonnetにフォールバック")
    except Exception as e:
        print(f"    [WARN] GPT-5.5エラー: {e} → Claude Sonnetにフォールバック")
    return call_claude_sonnet(prompt)


def _build_mono_prompt(mono_type: str, section_name: str, body: str, config: dict = None) -> str:
    if config is None: config = {}
    info = MONO_PROMPTS[mono_type]
    rules_text = "\n".join(f"  ・{r}" for r in info["rules"])
    return f"""あなたはこの小説の「{info['label']}専門強化者」です。
{config.get("tone_rule", "")}
以下の文章の{info['label']}を強化してください。

【強化方針】
{info['desc']}

【強化ルール】
{rules_text}

【絶対に変えてはいけないもの】
・台詞（「」で囲まれた部分）は一字も変えない
・話者ラベル（▷キャラ名：）は一字も変えない
・【★五感】マーカーは削除しない
・既存の身体描写・行動描写の方向性
・設定・固有情報

前置きや説明は不要。強化済み文章のみ出力してください。

【対象文章：{section_name}】
{body}
"""


# ============================================================
# 手動処理リスト生成
# ============================================================

SPLIT_THRESHOLD = 5000  # この文字数を超えたら前後半に分割処理

MONO_MAX_CHUNK = 8000  # 各AIへの最大入力字数

def _split_mono_chunks(body: str, max_size: int = MONO_MAX_CHUNK) -> list:
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


def apply_mono_pass_chunked(mono_type: str, section_name: str,
                             body: str, config: dict, body_len: int) -> str:
    """テキストを3,000字単位チャンクに分割してモノローグ処理し結合する"""
    chunks = _split_mono_chunks(body)
    print(f"      → {len(chunks)}チャンク: {[len(c) for c in chunks]}字")

    info = MONO_PROMPTS[mono_type]
    ai   = info["ai"]
    results = []

    for i, chunk in enumerate(chunks):
        chunk_name = f"{section_name}（{i+1}/{len(chunks)}）"
        prompt = _build_mono_prompt(mono_type, chunk_name, chunk, config)

        if ai == "claude_sonnet":
            result = call_claude_sonnet(prompt)
        elif ai == "claude_haiku":
            result = call_claude_haiku(prompt)
        elif ai in ("gpt55_instinct", "gpt55_thinking"):
            effort = "medium" if ai == "gpt55_instinct" else "high"
            result = _call_gpt55(prompt, config, effort=effort, body_len=len(chunk))
        else:
            result = call_claude_sonnet(prompt)

        if result and len(result.strip()) > max(100, len(chunk) * 0.5):
            results.append(result)
        else:
            print(f"      [WARN] チャンク{i+1}：切れ検出 → 元文章を維持")
            results.append(chunk)

    return "\n\n".join(results)


METAPHOR_KEYWORDS = [
    "ように", "まるで", "かのよう", "溶け", "沈んで",
    "吸われ", "広がる", "消える", "残った", "光を",
    "染み", "浮かぶ", "張りつく", "滲む", "霞む",
    "重なる", "流れ", "静止", "貫く", "刺さる",
]

REI_KEYWORDS = [
    "礼は", "礼が", "礼の", "礼だけ", "礼を",
]

MIN_METAPHOR = 2

def mark_manual_candidates(body: str, max_markers: int = 10) -> str:
    """比喩・モノローグ候補箇所に★マーカーを挿入する（合計最大max_markers箇所）"""

    # 比喩キーワードと優先度（三人称視点のため★モノは使用しない）
    METAPHOR_SCORED = [
        ("ように見え", 3), ("かのように", 3), ("まるで", 3),
        ("ように", 2), ("かのよう", 2), ("溶け", 2), ("沈んで", 2),
        ("吸われ", 2), ("消える", 2), ("残った", 2),
        ("染み", 1), ("浮かぶ", 1), ("滲む", 1), ("霞む", 1),
        ("重なる", 1), ("流れ", 1), ("刺さる", 1), ("広がる", 1),
    ]

    lines = body.split("\n")
    metaphor_cands = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if (not stripped or
            stripped.startswith("▷") or
            stripped.startswith("「") or
            "【★" in stripped or
            len(stripped) < 10):
            continue
        m_score = sum(v for kw, v in METAPHOR_SCORED if kw in stripped)
        if m_score > 0:
            metaphor_cands.append((i, m_score, line))

    metaphor_cands.sort(key=lambda x: -x[1])
    selected_metaphor = set(idx for idx, _, _ in metaphor_cands[:max_markers])

    marked = []
    for i, line in enumerate(lines):
        if i in selected_metaphor:
            marked.append(line + "　【★比喩】")
        else:
            marked.append(line)

    if selected_metaphor:
        print(f"    [手動マーカー] 【★比喩】{len(selected_metaphor)}箇所（上限{max_markers}）")
    return "\n".join(marked)

def generate_manual_monologue_list(body: str, section_name: str) -> str:
    """Sudowrite・NovelAI手動処理用リストを生成"""

    # 比喩・詩的表現の候補を抽出
    METAPHOR_MARKERS = ["ように", "まるで", "かのよう", "溶け", "沈んで",
                        "吸われ", "広がる", "消える", "残った", "光を"]
    # 礼の発言直後の地の文（感情の痕跡）
    REI_CONTEXT = ["礼は", "礼が", "礼の"]

    lines = body.split("\n")
    metaphor_candidates = []
    rei_candidates      = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("「") or stripped.startswith("▷"):
            continue
        if any(kw in stripped for kw in METAPHOR_MARKERS):
            metaphor_candidates.append(f"  行{i+1}: {stripped[:60]}{'...' if len(stripped)>60 else ''}")
        if any(kw in stripped for kw in REI_CONTEXT):
            rei_candidates.append(f"  行{i+1}: {stripped[:60]}{'...' if len(stripped)>60 else ''}")

    result = f"\n{'='*50}\n"
    result += f"【手動処理リスト（モノローグ）：{section_name}】\n"
    result += f"{'='*50}\n\n"

    result += "■ 比喩表現 → Sudowrite（Write > Prose Poem / Amplify）\n"
    result += "  指示：「以下の文章に映像的・詩的な比喩を加えてください」\n"
    if metaphor_candidates:
        result += "\n".join(metaphor_candidates) + "\n"
    else:
        result += "  （候補なし）\n"



    return result


# ============================================================
# ZA感情身体描写パス
# ============================================================

def _detect_scene_emotions(body: str, section_name: str) -> list:
    """本文から支配的感情を最大3つ検出する（軽量パス）"""
    if not ZA_EMOTIONS:
        return []

    emotion_list = "・".join(list(ZA_EMOTIONS.keys()))
    prompt = f"""以下の小説の一節を読み、このシーンでキャラクターが経験している
支配的な感情を最大3つ選んでください。

【感情リスト】
{emotion_list}

【制約】
・上記リストから選ぶ（リストにない感情は選ばない）
・最も強い感情から順に列挙
・感情名のみをカンマ区切りで出力（例：疑念,緊張,怒り）
・説明・前置き不要

【本文（{section_name}）】
{body[:2000]}
"""
    result = call_claude_sonnet(prompt)
    if not result:
        return []
    # カンマ区切りで分割、ZA_EMOTIONSに存在する感情のみ
    emotions = [e.strip() for e in result.strip().split(',')]
    return [e for e in emotions if e in ZA_EMOTIONS][:3]


def _build_body_prompt(body: str, section_name: str, emotions: list) -> str:
    """感情ごとの外的シグナルを参照して身体描写追加プロンプトを生成"""
    # ZAから外的シグナルを収集
    za_refs = []
    for emotion in emotions:
        if emotion in ZA_EMOTIONS:
            signals = ZA_EMOTIONS[emotion]["external"][:8]
            hint = ZA_EMOTIONS[emotion].get("hint", "")
            signals_text = "\n".join(f"    ・{s}" for s in signals)
            za_refs.append(
                f"  【{emotion}】\n{signals_text}"
                + (f"\n  ヒント：{hint[:100]}" if hint else "")
            )

    za_section = "\n".join(za_refs) if za_refs else "（感情データなし）"

    return f"""あなたはこの小説の「身体描写強化者」です。
以下の感情身体描写リストを参考に、本文中のキャラクターの身体反応描写を強化してください。

【検出された感情と身体反応リスト】
{za_section}

【追加ルール】
・1セクションにつき最大5箇所のみ追加（少ないほど良い）
・感情を直接書かない（「悲しかった」禁止。身体の動きで示す）
・俯瞰カメラ視点を維持（「碧は感じた」等の内側描写禁止）
・既存の身体描写と重複しない
・1〜2文の短い追加のみ（長い説明文は禁止）
・セリフ（▷キャラ：「」）は一切変えない
・三人称視点を崩さない
・文体（短文・体言止め）を維持する
・AIっぽい比喩表現（「まるで〜のように」等）は使わない
・【省略禁止】本文の全ての部分を出力すること。前半・後半問わず同等の密度で処理すること。後半になるにつれて文章量が減ることは禁止

【本文（{section_name}）】
{body}
"""


def _apply_body_pass(body: str, section_name: str,
                     body_len: int, is_third_person: bool) -> str:
    """感情身体描写パスを実行して本文を返す"""
    if not ZA_EMOTIONS or not is_third_person:
        return body

    # Step1: 感情検出
    emotions = _detect_scene_emotions(body, section_name)
    if not emotions:
        print(f"    [身体] 感情検出なし → スキップ")
        return body

    print(f"    [身体] 検出感情: {', '.join(emotions)}")

    # Step2: 身体描写追加
    prompt = _build_body_prompt(body, section_name, emotions)
    result = call_claude_sonnet(prompt)

    if result and len(result.strip()) > max(100, body_len * 0.8):
        if len(result.strip()) > body_len * 1.3:
            print(f"    [WARN] 身体：元文字数比{len(result.strip())/body_len:.1%}超過 → スキップ")
            return body
        return result
    else:
        print(f"    [WARN] 身体：切れ検出 → スキップ")
        return body


# ============================================================
# S27出力の読み込み
# ============================================================

def load_prev_section(novel_type: str, section_index: int,
                      sections: list) -> tuple:
    base    = Path(__file__).parent.parent / "output"
    section = sections[section_index]

    for skill_dir, prefix in [
        ("s27_description", "s27"),
        ("s26_dialogue",    "s26"),
        ("s25_rhythm",      "s25"),
        ("s24_draft",       "s24"),
    ]:
        files = sorted(
            (base / skill_dir).glob(
                f"{prefix}_{novel_type}_{section['index']}_*.md"
            ),
            reverse=True
        )
        files = [f for f in files if "manual" not in f.name
                 and "sudowrite" not in f.name]
        if files:
            text = files[0].read_text(encoding="utf-8")
            body = text.split("---", 1)[-1].strip() if "---" in text else text
            print(f"  [INFO] 入力: {files[0].name}（{len(body):,}字）")
            return body, len(body)
    return "", 0


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

    # ── 視点モードの判定 ─────────────────────────────
    viewpoint = config.get("novel_viewpoint", "third_person")
    is_third_person = ("third" in viewpoint or "三人称" in viewpoint)
    if is_third_person:
        print("\n[S28] モノローグ強化スキル 開始（三人称モード）")
        print(f"  小説タイプ: {novel_type}")
        print(f"  処理: 全体文章（Sonnet）+ ZA感情身体描写（Sonnet）+ 比喩マーカー（Sudowrite手動）")
        print(f"  ※三人称視点のためキャラ個別モノローグパスはスキップ")
    else:
        print("\n[S28] モノローグ強化スキル 開始（一人称モード）")
        print(f"  小説タイプ: {novel_type}")
        print(f"  処理: 全体文章 + キャラ個別パス全実行")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results    = {}
    manual_all = ""

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/8] {section['name']} 処理中...")

        body, body_len = load_prev_section(novel_type, idx, sections)
        if not body:
            print(f"  [SKIP] 入力ファイルなし")
            continue

        # ── 前セクションの文脈を読み込み ────────────
        n_ctx = int(config.get("context_sections", 2))
        context_prev = _load_context_s28(novel_type, idx, n=n_ctx) if idx > 0 else ""
        if context_prev:
            print(f"    [文脈] 直近{n_ctx}セクションを注入")

        current  = body
        chunked  = body_len > SPLIT_THRESHOLD
        if chunked:
            print(f"    ※{body_len:,}字 > {SPLIT_THRESHOLD:,}字 → 前後半分割モードで処理")

        # ── ① 全体文章（Claude Sonnet） ────────────
        # 三人称・一人称共通で実行（8,000字以内のみ）
        if body_len <= 8000:
            print(f"    [全体] Claude Sonnet...")
            result = call_claude_sonnet(
                _build_mono_prompt("overall", section["name"], current, config)
            )
            if result and len(result.strip()) > max(100, body_len * 0.8):
                current = result
            elif result:
                print(f"    [WARN] 全体：切れ検出 → スキップ")
        else:
            print(f"    [全体] スキップ（{body_len:,}字 > 8,000字）")

        # ── ② 感情身体描写パス（ZA参照・三人称モードのみ） ──
        if is_third_person and ZA_EMOTIONS:
            print(f"    [身体] ZA感情身体描写パス...")
            current = _apply_body_pass(
                current, section["name"], body_len, is_third_person
            )
        elif not is_third_person:
            print(f"    [キャラ個別] 一人称モード：キャラ別モノローグパスを実行")
            pass


        # ── ⑤ マーカー挿入 + 手動処理リスト生成 ──────
        # novel_typeに応じて比喩マーカー上限を設定
        _metaphor_limits = {"short": 5, "medium": 10, "long": 10}
        _meta_max = _metaphor_limits.get(novel_type, 5)
        current = mark_manual_candidates(current, max_markers=_meta_max)
        manual_all += generate_manual_monologue_list(current, section["name"])

        results[section["key"]] = current
        char_count = len(current)
        print(f"  完了：{body_len:,}字 → {char_count:,}字（{char_count-body_len:+,}字）")

        # ファイル保存
        filepath = OUTPUT_DIR / f"s28_{novel_type}_{section['index']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# モノローグ強化済み：{section['name']}\n"
                    f"実行日時：{timestamp}\n"
                    f"文字数：{char_count:,}字\n\n---\n\n{current}")
        print(f"  [OK] Saved: {filepath.name}")

        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_モノローグ強化")},
                "スキル":     {"rich_text": txt("S28_モノローグ強化")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select": {"name": "未使用"}},
            }, f"モノローグ強化：{section['name']}", current)

    # 手動処理リスト保存
    if manual_all:
        # セクション番号を取得（ループ変数idxから）
        manual_path = OUTPUT_DIR / f"s28_{novel_type}_manual_list_{section['index']}_{timestamp}.md"
        with open(manual_path, "w", encoding="utf-8") as f:
            f.write(f"# 手動処理リスト（S28モノローグ強化）\n"
                    f"実行日時：{timestamp}\n\n{manual_all}")
        print(f"\n  [手動リスト] Saved: {manual_path.name}")
        print(f"  比喩 → Sudowrite（Prose Poem / Amplify）で処理してください")

    total = sum(len(v) for v in results.values())
    print(f"\n[S28] 完了 / 合計文字数: {total:,}字")
    print("  次のステップ: S29（整合性チェック）")
    print(f"  コマンド例: python run_pipeline.py --skill 29 --type {novel_type}")

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
