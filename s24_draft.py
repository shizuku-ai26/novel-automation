# -*- coding: utf-8 -*-
"""
S24：初版文章生成スキル
呼び出し：python run_pipeline.py --skill 24 --type short --section N
役割：S23のシーン別プロット設計を受け取り、セクション単位で
     初版文章を生成する。

生成ルール（絶対遵守）：
  ・説明禁止（「〜だった」「〜のせいで」などの因果説明を避ける）
  ・感情を直接書かない（「悲しかった」→行動・身体描写で示す）
  ・五感優先（視覚・聴覚・触覚・嗅覚・味覚を意識する）
  ・余白を残す（全てを説明しない）
  ・台詞説明禁止（「〜と彼女は言った」の後に感情説明しない）

セクション構成（short）：
  0: prologue（プロローグ）
  1: ch1（第1章）
  2: ch2_3（第2〜3章）
  3: ch4_5（第4〜5章）
  4: midpoint（ミッドポイント）
  5: ch6_7（第6〜7章）
  6: turning（転）
  7: ch9_10（第9〜10章）
  8: epilogue（エピローグ）

次ステップ：S25〜S27（文章ブラッシュアップ）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)

# OpenAI API連携（利用可能な場合）
def _call_writing_ai(prompt: str, config: dict) -> str:
    """
    初版文章生成に使用するAIを決定して呼び出す。
    config.yaml の writing_ai で切り替え可能。
    
    writing_ai:
      openai  → OpenAI o1/o3（最高品質・要APIキー設定）
      claude  → Claude Sonnet（デフォルト・すぐ使える）
    """
    writing_ai = config.get("writing_ai", "claude")
    
    if writing_ai == "openai":
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "common"))
            from openai_utils import call_openai_thinking
            model = config.get("openai_model", "o3")
            effort = config.get("reasoning_effort", "high")
            # 目標文字数に応じてmax_tokensを動的に設定
            # 日本語1文字≒2トークン + reasoning用に3倍のバッファ
            target = config.get("_section_target", 2000)
            max_tok = max(8000, target * 6)
            print(f"    使用AI: OpenAI {model}（max_tokens={max_tok:,}）")
            return call_openai_thinking(
                prompt, model=model,
                reasoning_effort=effort,
                max_tokens=max_tok
            )
        except ImportError as e:
            print(f"    [WARN] OpenAI未インストール: {e}")
            print("    Claude Sonnetにフォールバック")
        except (ValueError, RuntimeError) as e:
            print(f"    [WARN] {e}")
            print("    Claude Sonnetにフォールバック")
    
    print("    使用AI: Claude Sonnet")
    return call_claude_sonnet(prompt)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s24_draft"


# ============================================================
# All ファイル管理（文章の流れ維持）
# ============================================================

def _get_all_filepath_s24(novel_type: str) -> Path:
    return OUTPUT_DIR / f"s24_all_{novel_type}.md"


def _update_all_file_s24(novel_type: str, section_idx: int,
                     section_name: str, content: str) -> None:
    all_path = _get_all_filepath_s24(novel_type)
    separator = f"\n\n{'='*60}\n[Section {section_idx}：{section_name}]\n{'='*60}\n"
    if all_path.exists():
        existing = all_path.read_text(encoding="utf-8")
        marker = f"[Section {section_idx}："
        if marker in existing:
            cut_pos = existing.find(marker)
            existing = existing[:cut_pos].rstrip()
        all_path.write_text(existing + separator + content, encoding="utf-8")
    else:
        header = f"# S24 全セクション統合（{novel_type})\n"
        all_path.write_text(header + separator + content, encoding="utf-8")


def _load_context_s24(novel_type: str, current_idx: int, n: int = 2) -> str:
    all_path = _get_all_filepath_s24(novel_type)
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

# セクション定義
SECTIONS = {
    "short": [
        {"index": 0, "key": "prologue",  "name": "プロローグ",     "target": 1000},
        {"index": 1, "key": "ch1",       "name": "第1章",          "target": 4000},
        {"index": 2, "key": "ch2_3",     "name": "第2〜3章",       "target": 8000},
        {"index": 3, "key": "ch4_5",     "name": "第4〜5章",       "target": 8000},
        {"index": 4, "key": "midpoint",  "name": "ミッドポイント",  "target": 2000},
        {"index": 5, "key": "ch6_7",     "name": "第6〜7章",       "target": 8000},
        {"index": 6, "key": "turning",   "name": "転",             "target": 2000},
        {"index": 7, "key": "ch9_10",    "name": "第9〜10章",      "target": 10000},
        {"index": 8, "key": "epilogue",  "name": "エピローグ",     "target": 2000},
    ],
    "medium": [
        {"index": 0, "key": "prologue",  "name": "プロローグ",     "target": 1500},
        {"index": 1, "key": "ch1_2",     "name": "第1〜2章",       "target": 8000},
        {"index": 2, "key": "ch3_6",     "name": "第3〜6章",       "target": 20000},
        {"index": 3, "key": "midpoint",  "name": "ミッドポイント",  "target": 3000},
        {"index": 4, "key": "ch8_10",    "name": "第8〜10章",      "target": 20000},
        {"index": 5, "key": "turning",   "name": "転",             "target": 3000},
        {"index": 6, "key": "ch12_14",   "name": "第12〜14章",     "target": 20000},
        {"index": 7, "key": "epilogue",  "name": "エピローグ",     "target": 2000},
    ],
}

# 生成ルール（プロンプト内で参照）
WRITING_RULES = """
【初版文章生成ルール（絶対遵守）】

■ 禁止事項
  ❌ 説明禁止：「〜だったから」「〜のせいで」等の因果説明
  ❌ 感情直描禁止：「悲しかった」「怖かった」「嬉しかった」
  ❌ 台詞説明禁止：「と彼女は悲しそうに言った」
  ❌ 内的独白の多用：「〜だと思った」が3文以上続く
  ❌ 「ため」「ので」の多用：因果関係の過剰説明
  ❌ 顕微鏡的身体描写：「右手の人差し指の第二関節が白くなるほど」のような過剰な精細描写
  ❌ カメラ記述スタイル：「蛍光灯の光が均等に満たす。影の向きが同じ。」のようなステージ指示書調

■ 推奨事項
  ✅ 身体描写で感情を示す：手が震える・息が止まる・目を逸らす
  ✅ 五感を使う：音・匂い・温度・触感・視覚を意識する
  ✅ 短文でテンポを作る（特に緊張場面）
  ✅ 余白を残す：重要な場面こそ「書かない」
  ✅ 台詞は「地の文なし」でも成立させる
  ✅ 視点を固定する（三人称限定・蓮視点）

■ 文体
  ・三人称限定視点（蓮の視点のみ）
  ・ライトノベルのリズム：読みやすく、テンポよく
  ・比喩は適度に。過剰な比喩はAI臭になる

━━━━━━━━━━━━━━━━━━━━━━━━━━━

【カジュアル文体ガイド（必読・全章共通）】

◆ セリフの原則
この物語の主人公・日暮蓮は16歳の高校生男子。
会話は「現代の高校生らしい自然なカジュアル語」で書くこと。

■ 蓮（16歳・男）のセリフ
  ✅ 「なんで来るの」「ちょっと待って」「それって本当？」「やめてよ」
  ✅ 語尾：だよ・じゃん・かな・だって・よ・ね・か？
  ❌ 「それは本当のことですか」「あなたは何者ですか」「私には理解できません」
  ❌ 文語・です・ます調（佐和子への反論時も崩さず話す）

■ ハクのセリフ（極力短く・子どもの語彙）
  ✅ 「れん、いる」「さむい」「そと」「あかるい」「いやだ」
  ✅ 2〜4語で一文。助詞を省く。
  ❌ 5語以上の文・複雑な文法・感情の説明

■ 佐和子（42歳・NPO代表）のセリフ
  ✅ 「外は、ハクさんには難しいんです」「記録を見てください」「あなたも、同じでしょう」
  ✅ 専門家らしさ＋温かみのある丁寧語。冷たくない。
  ❌ 悪役的な明確な脅しや命令口調

■ 遠田（38歳・寡黙）のセリフ
  ✅ 「これを」「行ける」「待っていた」（最小限）
  ✅ 多くて1文。ほとんど話さない。
  ❌ 長い説明・感情の表明・謝罪や弁明

◆ 地の文の原則
  ・身体描写は「感情の出力」として使う。精細な観察描写にしない。
  ✅ 「気づいたら、窓に手をかけていた」
  ❌ 「右手の中指と薬指が窓のクレセント錠の金属面に触れ、指先が白くなる」
  ・一文のリズム：短文（8〜15字）と中文（20〜35字）を交互に使う
  ・「ただ」「それだけ」「それだけだった」は余白として有効
"""

# セクション別の追加制約（どんでん返し保護）
SECTION_CONSTRAINTS = {
    5: """【第6〜7章専用制約（絶対遵守）】
❌ 遠田の正体・目的を明かさない
❌ 「よあけのまえ」の帰還抑制処置を明示しない
❌ ハクが「帰りたい」と言語で告白するシーンを書かない

✅ 第6〜7章の正しい役割：
  ・ハクの発光が静まったとき、蓮が「よかった」と安堵するシーン（E-3）を入れる
  ・「大丈夫、ここにいるから」という蓮の言葉でハクが落ち着く場面を入れる（最も深い錠前）
  ・遠田が蓮の行動の周辺に複数回現れるが介入しない描写を入れる
  ・「よあけのまえ」の名前の意味を誰かが一言だけ言及する（「夜明けを待つ場所、だそうです」）
  ・ハクの発光が「窓の方向に向いていた」一行を自然に埋め込む

✅ 第6〜7章の終わりの状態：
  ・蓮はまだ「ハクを守っている自分が正しい」と信じている
  ・遠田は「不気味な追跡者」のままで正体不明
  ・転の準備として最高の緊張が積み上がっている
""",
    4: """【ミッドポイント専用制約（絶対遵守）】
❌ 遠田がハクの味方だという描写・示唆を書かない
❌ 「よあけのまえ」の帰還抑制の真実を明かさない
❌ 佐和子を「明らかに悪役」として描かない

✅ ミッドポイントの正しい役割：
  ・「よあけのまえ」の施設で鍵のかかった部屋を蓮が発見→佐和子を問い詰める（感情強度8）
  ・佐和子の台詞：「ここにいる方が安全です。外は——ハクが理解できないものだらけで」（D-1）
  ・佐和子が「最初は夜中に窓を叩いていた。今はもう落ち着いた」と語る（I-2）
  ・佐和子が施設の鍵束を持っている手を蓮の視線が一瞬捉える（C-1）
  ・佐和子が静かに「あなたは違うと言えますか」と返す（→宙吊りで終わる）

✅ ミッドポイント後の状態：
  ・蓮の目的が「ハクを匿う」→「ハクを組織Aから解放する」に変化
  ・読者も蓮と同じ怒りを持ち「佐和子が悪だ」と信じている状態
""",
    6: """【転（どんでん返し）専用制約（絶対遵守）】

【前提】転まで、読者は「遠田が脅威で佐和子が保護者」と信じている。

✅ 転の正しい構造：
  ・蓮が佐和子を問い詰めている最中に遠田が一枚の記録用紙を差し出す
  ・記録の内容：「帰還反応の抑制処置：実施日（蓮とハクが出会った翌日）・承認者（霧島佐和子）」
  ・蓮がその日付を三回読み直す（U-2余白：感情を一切書かない）
  ・ハクが発光し始める→蓮が手を伸ばす→ハクが手を引き剥がす
  ・「佐和子の施設の鍵」と「蓮の窓を閉める手」が同じ構造だったことが暴かれる

✅ S18の伏線を一斉回収する（E-1・E-3・I-1・I-2・D-1・M-1）
✅ U-2余白：転直後の蓮の感情を一切書かない。日付を三回読む・視線が床に落ちる、だけ
✅ 佐和子は崩れない・言い訳しない。「……それが、あなたには縛っているように見えるのですか」

❌ 「蓮は気づいた」「蓮は理解した」等の認識説明を書かない
❌ 佐和子を「悪人として断罪する」展開にしない（善意のまま立っている）
❌ 遠田に説明・謝罪・感情表明をさせない（記録用紙を差し出すだけ）
❌ ハクに「帰りたかった」等の言語説明をさせない
""",
    7: """【結（第9〜10章）専用制約（絶対遵守）】
✅ どん底から再起のきっかけ：ハクが蓮の手の甲に自分の手を一瞬だけ乗せてから引く
✅ 蓮の問いかけ：「……外、行く？」（最小限の言葉）
✅ クライマックス：窓のクレセント錠を蓮が回す→窓が開く→ハクが光の中に消える
✅ D-2最終回収：ハクが「れん、いる」と最後に言う→蓮が「そうだよ、いる」と初めて返す
✅ C-1回収：蓮が自分の手を見る（佐和子の「握った鍵の手」と重なる構図）
✅ E-2回収：遠田への嫌悪感の正体を蓮が静かに受け取る（言語化なし）

❌ 「手放すことを決めた理由」を言語化させない
❌ 「正しかった」「赦せた」「すっきりした」等の解決宣言を書かない
❌ S13欠落制約：欠落を言語化させない・行動変化のみで示す
""",
    8: """【エピローグ専用制約（絶対遵守）】
✅ プロローグと同じ部屋・同じ窓・今度は窓が開いている
✅ カーテンが朝の風に少しだけ揺れる
✅ 蓮の手は空っぽ・震えは止まっているかまだ続いているか蓮にもわからない
✅ M-2完成：窓が開いている一事実のみ
✅ 最後の1文：「窓には、もう鍵がかかっていなかった。私がはずしたのか、最初からそうだったのか——今度は、そのどちらでもいいと思えた。」

❌ 「よかった」「正しかった」等の評価・解決を書かない
❌ ハクへの想いを言語化させない
❌ 「問いを持ち続ける」という直接表現を書かない
""",
}

# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s10": base / "s10_character"  / f"s10_character_latest_{novel_type}.md",
        "s21": base / "s21_margin"     / f"s21_margin_latest_{novel_type}.md",
        "s22": base / "s22_scene_emotion" / f"s22_emotion_latest_{novel_type}.md",
        "s23": base / "s23_scene_plot" / f"s23_scene_latest_{novel_type}.md",
    }
    limits = {"s10": 3000, "s21": 1500, "s22": 1500, "s23": 3000}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""

    # Bible（確定事実）を読み込む
    bible = base.parent / "output" / f"bible_{novel_type}.md"
    if bible.exists():
        results["bible"] = bible.read_text(encoding="utf-8")[:1000]
        print("  [INFO] Bible: 読み込み済み")
    else:
        results["bible"] = ""

    # 前セクションのテキストを読み込む（継続性確保）
    results["prev_section"] = ""

    return results


def load_prev_section_text(novel_type: str, section_index: int,
                            sections: list) -> str:
    """前セクションの末尾300文字を読み込む（継続性確保）"""
    if section_index == 0:
        return ""
    prev_idx = sections[section_index - 1]["index"]
    prev_files = sorted(
        OUTPUT_DIR.glob(f"s24_{novel_type}_{prev_idx}_*.md"),
        reverse=True
    )
    if prev_files:
        text = prev_files[0].read_text(encoding="utf-8")
        return text[-300:]
    return ""


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(section: dict, prev: dict,
                 prev_text: str, contest_key: str,
                 world_setting: str = "", setting_confirmed: dict = None) -> str:

    # セクション別制約（どんでん返し保護）
    section_constraint = SECTION_CONSTRAINTS.get(section["index"], "")

    # コンテスト別の文章指針
    contest_note = ""
    if contest_key == "note":
        contest_note = "※note：冒頭3行に感情フック必須。読みやすい改行。目標文字数はセクション設定に従うこと（上書き禁止）。"
    elif contest_key == "kakugawa_chara":
        contest_note = "※角川：主人公の魅力を前面に。会話を活かしてキャラを立てる。"
    elif contest_key == "kakuyomu":
        contest_note = "※カクヨム：テンポ最優先。第一話は特に引きを強く。"
    elif contest_key == "everystory":
        contest_note = "※エブリスタ：コマ映えする描写。短文テンポ。感情爆発を惜しまない。"

    prev_context = f"\n【前セクションの末尾（継続性確保）】\n{prev_text}\n" if prev_text else ""

    # 確定済み世界観・設定セクション
    world_lines = []
    if world_setting:
        world_lines.append(f"・世界観：{world_setting}")
    if setting_confirmed:
        if setting_confirmed.get("organization_type"):
            world_lines.append(f"・組織A：{setting_confirmed['organization_type']}")
        if setting_confirmed.get("monster_return_place"):
            world_lines.append(f"・怪物の帰る場所：{setting_confirmed['monster_return_place']}")
        if setting_confirmed.get("monster_return_sign"):
            world_lines.append(f"・怪物の帰還サイン：{setting_confirmed['monster_return_sign']}")
    world_section = (
        "【確定済み世界観・設定（本文生成に必ず反映）】\n"
        + "\n".join(world_lines) + "\n"
    ) if world_lines else ""

    return f"""あなたはこの小説の「初稿ライター」です。
以下の設計書を忠実に実行し、「{section['name']}」の初版文章を生成してください。

{WRITING_RULES}
{section_constraint}
目標文字数：約{section['target']:,}文字
{contest_note}
{world_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S23 シーン別プロット設計（この章の設計）】
{prev["s23"]}

【キャラクター設計（口調・行動パターン）】
{prev["s10"]}

【感情波形（この章の感情状態）】
{prev["s22"]}
{prev.get("s22_rules", "")}

【余白設計（書かない場所の指示）】
{prev["s21"]}
{prev.get("s21_rules", "")}

【固定事実Bible（矛盾禁止）】
{prev["bible"]}
{prev_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【出力形式】
・地の文と台詞のみ出力する
・セクション番号（▼シーン1 等）は付けてよい
・前置き・後書き・コメントは一切不要
・文字数が目標に満たない場合は描写を丁寧にする
・文字数が超過する場合は削る（冗長な説明から）

では、「{section['name']}」の文章を生成してください。
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None, section_index: int = None) -> dict:
    if config is None:
        config = load_config()

    token       = config["api_keys"]["notion_token"]
    plot_db     = config["notion_dbs"].get("plot_db", "")
    novel_type  = config.get("novel_type", "short")
    contest_key = config.get("contest", None)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    sections = SECTIONS.get(novel_type, SECTIONS["short"])

    # セクション指定がない場合は全セクション実行
    if section_index is None:
        targets = list(range(len(sections)))
    else:
        targets = [section_index]

    print("\n[S24] 初版文章生成スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  対象セクション: {[sections[i]['name'] for i in targets]}")

    prev = load_prev_outputs(novel_type)

    # fix④: S21のAI臭除去チェックリスト以降を末尾から抽出
    from pathlib import Path as _Path
    _s21_path = _Path(__file__).parent.parent / "output" / "s21_margin" \
               / f"s21_margin_latest_{novel_type}.md"
    if _s21_path.exists():
        _s21_full = _s21_path.read_text(encoding="utf-8")
        _idx = _s21_full.find("## ■ AI臭除去チェックリスト")
        prev["s21_rules"] = _s21_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s21_rules"] = ""

    # fix⑤: S22のS24引き渡しパラメータを末尾から抽出
    _s22_path = _Path(__file__).parent.parent / "output" / "s22_scene_emotion" \
               / f"s22_emotion_latest_{novel_type}.md"
    if _s22_path.exists():
        _s22_full = _s22_path.read_text(encoding="utf-8")
        _idx22 = _s22_full.rfind("## ■ S23（シーン別プロット設計）への引き渡しパラメータ")
        prev["s22_rules"] = _s22_full[_idx22:] if _idx22 >= 0 else ""
    else:
        prev["s22_rules"] = ""

    # fix⑥: S23のセクション別抽出マップ（セクション番号→章ヘッダー）
    _S23_SECTION_HEADERS = {
        0: "## ■ プロローグ", 1: "## ■ 第1章", 2: "## ■ 第2〜3章",
        3: "## ■ 第4〜5章", 4: "## ■ ミッドポイント", 5: "## ■ 第6〜7章",
        6: "## ■ 転", 7: "## ■ 第9〜10章", 8: "## ■ エピローグ",
    }
    _s23_path = _Path(__file__).parent.parent / "output" / "s23_scene_plot" \
               / f"s23_scene_latest_{novel_type}.md"
    _s23_full = _s23_path.read_text(encoding="utf-8") if _s23_path.exists() else ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    for idx in targets:
        section = sections[idx]
        print(f"\n  [{section['index']}/{len(sections)-1}] {section['name']} 生成中...")
        print(f"  目標文字数: {section['target']:,}字")

        prev_text = load_prev_section_text(novel_type, idx, sections)

        # fix⑥: S23から当該セクションの設計だけを抽出してprevに注入
        if _s23_full:
            _header = _S23_SECTION_HEADERS.get(idx, "")
            _next_headers = [h for i, h in _S23_SECTION_HEADERS.items() if i > idx]
            _start = _s23_full.find(_header) if _header else -1
            if _start >= 0:
                _end = len(_s23_full)
                for _nh in _next_headers:
                    _p = _s23_full.find(_nh, _start + 1)
                    if _p > 0:
                        _end = min(_end, _p)
                        break
                prev["s23"] = _s23_full[_start:_end][:4000]
            else:
                prev["s23"] = _s23_full[:3000]

        # ── All ファイルから前セクション文脈を注入 ──
        n_ctx = int(config.get("context_sections", 2))
        context_all = _load_context_s24(novel_type, idx, n=n_ctx) if idx > 0 else ""
        if context_all:
            print(f"    [文脈] 直近{n_ctx}セクションを注入（s24_all）")
        world_setting    = config.get("world_setting", "")
        setting_confirmed = config.get("setting_confirmed", {})
        prompt = build_prompt(section, prev, prev_text + "\n" + context_all if context_all else prev_text, contest_key, world_setting, setting_confirmed)

        # 目標文字数をconfigに注入（max_tokens動的計算用）
        config["_section_target"] = section["target"]
        draft = _call_writing_ai(prompt, config)

        # 空レスポンス検知 → max_tokensを2倍にしてOpenAI Thinkingで再試行
        if not draft or len(draft.strip()) < 100:
            print(f"  [WARN] 生成結果が空（{len(draft)}字）。max_tokensを2倍にしてThinkingで再試行...")
            config["_section_target"] = section["target"] * 2
            draft = _call_writing_ai(prompt, config)
            # 2回目も空の場合のみClaude Sonnetにフォールバック
            if not draft or len(draft.strip()) < 100:
                print(f"  [WARN] 再試行も空。Claude Sonnetにフォールバック...")
                draft = call_claude_sonnet(prompt)

        results[section["key"]] = draft
        char_count = len(draft)
        print(f"  生成文字数: {char_count:,}字")

        # ファイル保存（命名: s24_short_0_YYYYMMDD.md ～ s24_short_8_YYYYMMDD.md）
        filepath = OUTPUT_DIR / f"s24_{novel_type}_{section['index']}_{timestamp}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 初版文章：{section['name']}\n"
                    f"実行日時：{timestamp}\n"
                    f"文字数：{char_count:,}字\n\n---\n\n{draft}")
        print(f"  [OK] Saved: {filepath.name}")

        # ── All ファイル更新 ──────────────────────
        _update_all_file_s24(novel_type, idx, section["name"], draft)
        print(f"  [OK] s24_all_{novel_type}.md 更新")

        # Notion保存
        if plot_db:
            notion_create_page_long(token, plot_db, {
                "名前":       {"title": txt(f"{timestamp}_{section['name']}_初版")},
                "スキル":     {"rich_text": txt("S24_初版文章生成")},
                "小説タイプ": {"rich_text": txt(novel_type)},
                "ステータス": {"select": {"name": "未使用"}},
            }, f"初版：{section['name']}", draft)

    total_chars = sum(len(v) for v in results.values())
    print(f"\n[S24] 完了 / 合計文字数: {total_chars:,}字")
    print("  次のステップ: S25〜S27（文章ブラッシュアップ）")
    print(f"  コマンド例: python run_pipeline.py --skill 25 --type {novel_type} --section-name prologue")

    return {"result": results, "timestamp": timestamp, "total_chars": total_chars}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--section", type=int, default=None,
                        help="セクション番号（0〜8・省略時は全セクション）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"] = args.type
    _config["contest"]    = args.contest
    run(config=_config, section_index=args.section)
