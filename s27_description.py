# -*- coding: utf-8 -*-
"""
S27：情景描写強化スキル（場面別4種）
呼び出し：python run_pipeline.py --skill 27 --type short --section 0

情景4種の割り当て：
  世界観描写（白の家・施設全体） → Gemini Pro        ← API自動
  背景描写（廊下・食堂・室内）   → Gemini思考        ← API自動
  人物描写（湊・礼・冬子）       → Claude Sonnet     ← API自動
  五感描写（音・匂い・温度）     → Sudowrite         ← 手動処理リスト出力

次ステップ：S28（モノローグ強化）
"""



import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s27_description"

# ============================================================
# All ファイル管理（文章の流れ維持）
# ============================================================

def _get_all_filepath_s27(novel_type: str) -> Path:
    return OUTPUT_DIR / f"s27_all_{novel_type}.md"


def _update_all_file_s27(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    all_path = _get_all_filepath_s27(novel_type)
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
        header = f"# S27 全セクション統合（{novel_type})\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context_s27(novel_type: str, current_idx: int, n: int = 2) -> str:
    all_path = _get_all_filepath_s27(novel_type)
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
# 描写強化プロンプト定義
# ============================================================

DESC_PROMPTS = {
    "world": {
        "label": "世界観描写（現代都市・アパート・NPO施設）",
        "ai":    "gemini_pro",
        "desc":  "早朝の住宅街・アパートの廊下・NPO「よあけのまえ」の古い建物が持つ"
                 "「善意と閉塞」の空気感を映像的に強化する。"
                 "夜明け前という時間軸の持つ非日常性と、閉じた窓と開いた窓の対比を描く。",
        "rules": [
            "アスファルト・街灯・電柱・路地・自販機など都市の早朝ディテールを強化",
            "NPO施設の「小さな善意」を感じさせる小道具（植木鉢・古い木の看板・子どもの絵）",
            "「閉じた窓と開いた窓」の対比を物語全体のモチーフとして意識的に描写",
            "夜明け前の青・白・灰色の色調を統一感ある描写で強化",
            "地の文のみ強化。台詞は一切変えない",
            "【厳守】文字数は元の±20%以内。絶対に超えない",
            "【AI臭禁止】観念的比喩を書かない。「〜かのようだ」「〜のように」等は禁止",
            "既存の短文リズム（1行1文・体言止め）を壊さない",
        ],
    },
    "bg": {
        "label": "背景描写（蓮の部屋・施設廊下・路地）",
        "ai":    "gemini_thinking",
        "desc":  "蓮の六畳のアパート・NPO「よあけのまえ」の廊下・早朝の路地の"
                 "具体的な背景描写を強化する。",
        "rules": [
            "蓮の部屋：カーテンの隙間の光・窓の鍵・毛布の湿り気・充電ケーブル・缶コーヒー",
            "施設の廊下：ドアノブの違い・鍵の新旧・木の棚と記録ノート・床板の音",
            "路地：夜明け前のアスファルトの湿り・街灯の光の角度・電柱の根元",
            "時間帯による光の変化を描写（夜明け前の青→朝の白→昼間の色）",
            "地の文のみ強化。台詞は一切変えない",
            "【厳守】文字数は元の±20%以内。絶対に超えない",
            "【AI臭禁止】観念的比喩を書かない。具体的な物と光と音のみ描写",
            "既存の短文リズム（1行1文・体言止め）を壊さない",
        ],
    },
    "person": {
        "label": "人物描写（蓮・ハク・佐和子・遠田）",
        "ai":    "claude_sonnet",
        "desc":  "登場人物の身体描写・仕草・存在感を強化する。"
                 "感情を直接書かずに身体と行動で表現する既存方針を維持しつつ深化。",
        "rules": [
            "蓮：鍵を確認する手・カーテンを閉める動作・毛布を横に置く判断・窓に触れて止まる指",
            "ハク：肩の発光の強弱・膝を抱える形・裸足の足先・指先がアスファルトや床に触れる感触",
            "佐和子：鍵束を握る手の力加減・袖口の折り方・視線の静けさ・一歩後ろに引かない立ち方",
            "遠田：踵を返す動作・記録用紙を差し出す手・背中・まばたきの少なさ",
            "「悲しい」「怖い」「嬉しい」等の感情語は絶対に使わない",
            "既存の身体描写をさらに具体化する方向で強化",
            "地の文のみ強化。台詞は一切変えない",
            "【厳守】文字数は元の±20%以内。絶対に超えない",
            "【AI臭禁止】観念的比喩を書かない。身体・物・動作のみ描写",
            "既存の短文リズム（1行1文・体言止め）を壊さない",
        ],
    },
    "sense": {
        "label": "五感描写（音・匂い・温度）",
        "ai":    "sudowrite",
        "desc":  "音・匂い・温度・触感の五感描写を強化する（Sudowrite手動処理）",
        "rules": [
            "洗剤の匂い・乾いた米の匂い・消毒液・古い木の匂い",
            "夜明け前の冷たい空気・アスファルトの湿った匂い",
            "鍵の金属の冷たさ・毛布の湿り気・缶コーヒーのぬるい金属感",
            "鍵の「かち」という浅い音・毛布がこすれる音・窓のレールの引っかかり",
            "「よあけのまえ」の古い木と消毒液の混合と「外の朝の空気」の対比",
        ],
    },
}


# ============================================================
# API呼び出し関数
# ============================================================

def _call_gemini(prompt: str, config: dict,
                 model_type: str = "pro",
                 body_len: int = 2000) -> str:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
        from gemini_utils import call_gemini_thinking, load_gemini_config
        cfg = load_gemini_config()
        if model_type == "pro":
            model = "gemini-2.5-pro"
        else:
            model = cfg.get("model", "gemini-2.5-flash")
        # body_lenに基づいてmax_tokensを動的設定（日本語1文字≒2トークン×2倍バッファ）
        max_tok = max(8000, body_len * 4)
        print(f"    max_tokens={max_tok:,}")
        result = call_gemini_thinking(
            prompt, model=model, max_tokens=max_tok, config=config
        )
        # 出力が入力の30%未満なら切れていると判断してフォールバック
        if result and len(result.strip()) > max(100, body_len * 0.8):
            return result
        if result:
            print(f"    [WARN] Gemini出力が短すぎます（{len(result)}字 / 入力{body_len}字）→ Claude Sonnetにフォールバック")
        else:
            print(f"    [WARN] Gemini空レスポンス → Claude Sonnetにフォールバック")
    except Exception as e:
        print(f"    [WARN] Geminiエラー: {e} → Claude Sonnetにフォールバック")
    return call_claude_sonnet(prompt)



DESC_SPLIT_THRESHOLD = 5000

def _split_text_desc(body: str) -> tuple:
    mid = len(body) // 2
    split_pos = body.find("\n\n", mid)
    if split_pos == -1:
        split_pos = body.find("\n", mid)
    if split_pos == -1:
        split_pos = mid
    return body[:split_pos].strip(), body[split_pos:].strip()

CLAUDE_MAX_CHUNK = 3000  # Claude Sonnetへの最大入力字数

def _split_into_chunks(body: str, max_size: int = CLAUDE_MAX_CHUNK) -> list:
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

def _apply_desc_pass_chunked(call_fn, section_name: str, body: str, config: dict) -> str:
    chunks = _split_into_chunks(body)
    total = len(chunks)
    print(f"      → {total}チャンク分割: {[len(c) for c in chunks]}字")
    results = []
    for i, chunk in enumerate(chunks):
        chunk_name = f"{section_name}（{i+1}/{total}）"
        # chunk_index/total_chunksをconfigに乗せて渡す
        chunk_config = dict(config) if config else {}
        chunk_config["_chunk_index"] = i
        chunk_config["_total_chunks"] = total
        result = call_fn(chunk, chunk_name, chunk_config)
        if result and len(result.strip()) > max(100, len(chunk) * 0.85):
            results.append(result)
        else:
            print(f"      [WARN] チャンク{i+1}：切れ検出 → 元文章を維持")
            results.append(chunk)
    return "\n\n".join(results)

def _build_desc_prompt(desc_type: str, section_name: str, body: str, config: dict = None) -> str:
    if config is None: config = {}
    info = DESC_PROMPTS[desc_type]
    rules_text = "\n".join(f"  ・{r}" for r in info["rules"])
    input_len = len(body)
    max_len = int(input_len * 1.2)
    chunk_idx   = config.get("_chunk_index", 0)
    chunk_total = config.get("_total_chunks", 1)
    chunk_note  = f"（チャンク{chunk_idx+1}/{chunk_total}）" if chunk_total > 1 else ""
    return f"""あなたはこの小説の「{info['label']}専門強化者」です。
{config.get("tone_rule", "")}
【⚠ 文字数制限（絶対遵守）】入力文章は{input_len}字です。出力は最大{max_len}字まで。これを超えた場合は不合格です。
【⚠ AI臭禁止】「〜かのようだ」「〜のように」等の観念的比喩・説明的形容詞を追加しない。
【⚠ 省略・短縮禁止{chunk_note}】入力の最初から最後まで、全ての行を同等の密度で処理すること。後半になるにつれて処理が薄くなることは禁止。
以下の文章の{info['label']}を強化してください。

【強化方針】
{info['desc']}

【強化ルール】
{rules_text}

【絶対に変えてはいけないもの】
・台詞（「」で囲まれた部分）は一字も変えない
・話者ラベル（▷キャラ名：）は一字も変えない
・キャラクターの行動・感情の方向性
・伏線・設定の固有情報

前置きや説明は不要。強化済み文章のみ出力してください。

【対象文章：{section_name}】
{body}
"""


# ============================================================
# 五感描写 手動処理リスト生成
# ============================================================

def mark_sense_candidates(body: str, max_markers: int = 5) -> str:
    """本文中の五感強化候補箇所に【★五感】マーカーを挿入する（最大max_markers箇所）"""

    # キーワードと優先度スコア（高いほど優先）
    SENSE_SCORED = [
        # 優先度3：感情の転換点・身体接触・緊張のピーク
        ("指先", 3), ("指の", 3), ("手が", 3), ("手を", 3), ("握り", 3),
        ("震え", 3), ("止まった", 3), ("止まる", 3), ("静止", 3),
        ("触れる", 3), ("触れた", 3), ("擦れる", 3), ("食い込む", 3),
        # 優先度2：感覚描写のキーワード
        ("匂い", 2), ("冷たい", 2), ("冷たさ", 2), ("温かい", 2), ("温もり", 2),
        ("音が", 2), ("音を", 2), ("音だ", 2), ("音は", 2), ("聞こえ", 2),
        ("ざらつき", 2), ("ざらつく", 2), ("湿気", 2), ("乾いた", 2),
        ("光が", 2), ("光を", 2), ("光の", 2), ("影", 2),
        # 優先度1：背景・設定描写
        ("換気扇", 1), ("消毒液", 1), ("木の匂い", 1), ("廊下", 1),
        ("白い壁", 1), ("タイル", 1), ("絨毯", 1), ("窓", 1),
    ]
    SENSE_KEYWORDS = {kw: score for kw, score in SENSE_SCORED}

    lines = body.split("\n")
    candidates = []  # (行番号, スコア, 行テキスト)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if (not stripped or
            stripped.startswith("▷") or
            stripped.startswith("「") or
            "【★" in stripped or
            len(stripped) < 10):
            continue
        score = sum(v for kw, v in SENSE_KEYWORDS.items() if kw in stripped)
        if score > 0:
            candidates.append((i, score, line))

    # スコア降順でソートして上位max_markers件を選択
    candidates.sort(key=lambda x: -x[1])
    selected_lines = set(idx for idx, _, _ in candidates[:max_markers])

    marked = []
    for i, line in enumerate(lines):
        if i in selected_lines:
            marked.append(line + "　【★五感】")
        else:
            marked.append(line)

    actual = len(selected_lines)
    if actual > 0:
        print(f"    [五感マーカー] {actual}箇所（上限{max_markers}箇所）")
    return "\n".join(marked)

def generate_sense_list(body: str, section_name: str) -> str:
    """Sudowrite手動処理用：五感描写の強化候補箇所をリスト出力"""
    SENSE_KEYWORDS = [
        "匂い", "音が", "音を", "音だ", "音の", "音は",
        "冷たい", "冷たさ", "温かい", "温もり",
        "ざらつき", "ざらつく", "触れる", "擦れる",
        "聞こえ", "聞こえた", "消毒液", "洗剤",
        "換気扇", "秒針", "金属の", "紙の",
        "湿った", "乾いた",
    ]

    lines = body.split("\n")
    candidates = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("▷") or stripped.startswith("「"):
            continue
        if any(kw in stripped for kw in SENSE_KEYWORDS):
            # マーカーは除いて表示
            clean = stripped.replace("　【★五感】", "")
            candidates.append(
                f"  行{i+1}: {clean[:70]}{'...' if len(clean) > 70 else ''}"
            )

    result = f"\n{'='*50}\n"
    result += f"【五感描写 手動処理リスト：{section_name}】\n"
    result += f"{'='*50}\n\n"
    result += "■ Sudowrite（Amplify / Sensory機能）で強化する候補箇所\n"
    result += "  ※本文中の【★五感】マーカーが付いた行と対応しています\n\n"
    if candidates:
        result += "\n".join(candidates) + "\n"
    else:
        result += "  （このセクションに五感描写の強化候補なし）\n"

    result += "\n【Sudowrite操作手順】\n"
    result += "  1. 本文の【★五感】マーカーを探す\n"
    result += "  2. その行のテキストをSudowriteに貼り付け\n"
    result += "  3. 「Amplify」または「Sensory Details」で強化\n"
    result += "  4. 出力を3候補（匂い・音・触覚）に分けて個別評価する\n"
    result += "  5. 採用基準に従いパーツを選別して本文に組み込む\n"
    result += "  6. 【★五感】マーカーを削除\n"
    result += "\n【Sudowrite出力の評価基準】\n"
    result += "  ✅ 採用できるパーツ\n"
    result += "    ・空間・場所の匂い・音の描写（廊下・教室・職員室など）\n"
    result += "    ・「古い木の棚の乾いた匂い」等の具体的な無生物描写\n"
    result += "    ・文体に合う短文（15字以内が目安）\n"
    result += "  ❌ 採用できないパーツ（必ず除外）\n"
    result += "    ・視点崩壊：人物が触れていない物に触れた描写\n"
    result += "    ・視点崩壊：蓮の内側の感覚（「痛みが走る」「温かく感じた」等）\n"
    result += "    ・感情の直接描写（「不安からにじみ出る汗」等）\n"
    result += "    ・英語直訳の擬人化（「廊下がフェルトのように音を吸収」等）\n"
    result += "    ・観念的比喩（「静寂が鼓膜を押しつぶす」「空虚な音」等）\n"
    result += "    ・読者への呼びかけ（「感じるだろう」等）\n"
    result += "  ⚠ 修正して使うパーツ\n"
    result += "    ・良い素材だが文が長い → 圧縮して使う\n"
    result += "    　例：「鍵の金属が指先を冷たく貫いていた」\n"
    result += "    　　→「鍵の金具は、冷たかった。」\n"
    result += "  🔒 元文のまま推奨（追加不要）\n"
    result += "    ・人物の身体描写（手・指・目・歩き方など）\n"
    result += "    ・元文が既に短文で完結している場合\n"

    return result


# ============================================================
# S26出力の読み込み
# ============================================================

def load_s26_section(novel_type: str, section_index: int,
                     sections: list) -> tuple:
    base = Path(__file__).parent.parent / "output"
    section = sections[section_index]

    # S26 → S25 → S24 の順でフォールバック
    for skill_dir, prefix in [
        ("s26_dialogue", "s26"),
        ("s25_rhythm",   "s25"),
        ("s24_draft",    "s24"),
    ]:
        files = sorted(
            (base / skill_dir).glob(
                f"{prefix}_{novel_type}_{section['index']}_*.md"
            ),
            reverse=True
        )
        # manual_listファイルを除外
        files = [f for f in files if "manual_list" not in f.name]
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

    print("\n[S27] 情景描写強化スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  API自動: 世界観（Gemini Pro）/ 背景（Gemini思考）/ 人物（Claude Sonnet）")
    print(f"  手動処理: 五感描写（Sudowrite）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results  = {}
    sense_all = ""

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/8] {section['name']} 処理中...")

        body, body_len = load_s26_section(novel_type, idx, sections)
        if not body:
            print(f"  [SKIP] 入力ファイルなし")
            continue

        # ── 前セクションの文脈を読み込み ────────────
        n_ctx = int(config.get("context_sections", 2))
        context_prev = _load_context_s27(novel_type, idx, n=n_ctx) if idx > 0 else ""
        if context_prev:
            print(f"    [文脈] 直近{n_ctx}セクションを注入")

        current = body

        # ── ① 世界観描写（Gemini Pro） ──────────────
        print(f"    [世界観] Gemini Pro...")
        prompt = _build_desc_prompt("world", section["name"], current, config)
        result = _call_gemini(prompt, config, model_type="pro", body_len=len(current))
        if result and len(result.strip()) > max(100, len(current) * 0.8):
            if len(result.strip()) > body_len * 1.2:
                print(f"    [WARN] 世界観：元文字数比{len(result.strip())/body_len:.1%}超過 → スキップ")
            else:
                current = result

        # ── ② 背景描写（Gemini思考） ──────────────
        print(f"    [背景] Gemini思考...")
        prompt = _build_desc_prompt("bg", section["name"], current, config)
        result = _call_gemini(prompt, config, model_type="thinking", body_len=len(current))
        if result and len(result.strip()) > max(100, len(current) * 0.8):
            if len(result.strip()) > body_len * 1.2:
                print(f"    [WARN] 背景：元文字数比{len(result.strip())/body_len:.1%}超過 → スキップ")
            else:
                current = result

        # ── ③ 人物描写（Claude Sonnet） ────────────
        _pre_person = current  # 累積チェック用スナップショット
        print(f"    [人物] Claude Sonnet...")
        _before_person = len(current)
        if len(current) > DESC_SPLIT_THRESHOLD:
            _result_person = _apply_desc_pass_chunked(
                lambda ch, sn, cfg: call_claude_sonnet(
                    _build_desc_prompt("person", sn, ch, cfg)),
                section["name"], current, config)
            if len(_result_person.strip()) > body_len * 1.2:
                print(f"    [WARN] 人物：元文字数比{len(_result_person.strip())/body_len:.1%}超過 → スキップ")
            else:
                current = _result_person
        else:
            prompt = _build_desc_prompt("person", section["name"], current, config)
            result = call_claude_sonnet(prompt)
            if result and len(result.strip()) > max(100, len(current) * 0.8):
                if len(result.strip()) > body_len * 1.5:
                    print(f"    [WARN] 人物：元文字数比{len(result.strip())/body_len:.1%}超過 → スキップ")
                else:
                    current = result
            elif result:
                print(f"    [WARN] 人物：切れ検出 → スキップ")

        # ── ④ 五感描写：本文マーキング＋リスト生成（Sudowrite手動） ───
        # novel_typeに応じて五感マーカー上限を設定
        _sense_limits = {"short": 5, "medium": 10, "long": 10}
        _sense_max = _sense_limits.get(novel_type, 5)
        # ── 累積超過チェック（全パス後）─────────────────
        if len(current) > body_len * 1.25:
            print(f"    [WARN] 累積超過：{len(current):,}字 / 元{body_len:,}字"
                  f"（{len(current)/body_len:.1%}）→ 人物パス前に戻します")
            current = _pre_person if "_pre_person" in dir() else current

        current = mark_sense_candidates(current, max_markers=_sense_max)
        sense = generate_sense_list(current, section["name"])
        sense_all += sense

        results[section["key"]] = current
        char_count = len(current)
        print(f"  完了：{body_len:,}字 → {char_count:,}字（{char_count - body_len:+,}字）")

        # ファイル保存
        filepath = OUTPUT_DIR / f"s27_{novel_type}_{section['index']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 情景描写強化済み：{section['name']}\n"
                    f"実行日時：{timestamp}\n"
                    f"文字数：{char_count:,}字\n\n---\n\n{current}")
        print(f"  [OK] Saved: {filepath.name}")

        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_情景強化")},
                "スキル":     {"rich_text": txt("S27_情景描写強化")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select": {"name": "未使用"}},
            }, f"情景描写強化：{section['name']}", current)

    # 五感描写手動リスト保存
    if sense_all:
        sense_path = OUTPUT_DIR / f"s27_{novel_type}_sudowrite_list_{section['index']}_{timestamp}.md"
        with open(sense_path, "w", encoding="utf-8") as f:
            f.write(f"# 五感描写手動処理リスト（Sudowrite）\n"
                    f"実行日時：{timestamp}\n\n{sense_all}")
        print(f"\n  [Sudowrite手動リスト] Saved: {sense_path.name}")

    total = sum(len(v) for v in results.values())
    print(f"\n[S27] 完了 / 合計文字数: {total:,}字")
    print("  次のステップ: S28（モノローグ強化）")
    print(f"  コマンド例: python run_pipeline.py --skill 28 --type {novel_type} --section 0")

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
