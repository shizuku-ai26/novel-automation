# -*- coding: utf-8 -*-
"""
S1：どんでん返し設計スキル（v2）
呼び出し：python run_pipeline.py --skill 1 --type short
役割：価値観反転タイプ（V1〜V7）を上位レイヤーとし、
     3匹のモンスター理論×10パターンを下位レイヤーとして抽選。
     技法A（逆行型動機）+ C（認知的盲点）を組み込み、
     S7（哲学的問い）連動用の「問いの種」をドラフト出力する。
     実行時に中テーマ型をデッキ方式で事前決定し、S9に引き渡す。

config.yaml 対応パラメータ:
  value_reversal: "V1"〜"V7" または 省略（省略時はランダム）
  novel_type: "short" / "medium" / "long"

tone_mode挙動：
  casual（デフォルト）：全10パターンから重み付き抽選（制限なし）
  hard              ：2:ドラウル / 3:ドラフラ / 6:ウルフラ / 7:フラウル の4パターンに限定
"""

import sys
import random
import re
import unicodedata
import json as _json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, save_output, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s01_plot_twist"
INPUT_DIR  = Path(__file__).parent.parent / "input"


# ============================================================
# 中テーマ事前決定（デッキ方式）
# ============================================================

def _load_type_names_brief() -> dict:
    """input/type*.txt からタイプID・名前・サマリ・ファイルパスを軽量ロード（S1専用）"""
    types = {}
    if not INPUT_DIR.exists():
        print(f"  [WARN] input/ディレクトリが見つかりません: {INPUT_DIR}")
        return types
    for filepath in sorted(INPUT_DIR.glob("type[0-9][0-9].txt")):
        try:
            content = filepath.read_text(encoding="utf-8")
            lines   = content.splitlines()
            first   = unicodedata.normalize("NFKC", lines[0].strip()) if lines else ""
            m_id    = re.search(r"【タイプ(\d+)】", first)
            m_name  = re.search(r"「(.+?)」", first)
            if not (m_id and m_name):
                continue
            type_id = int(m_id.group(1))
            name    = m_name.group(1)
            summary = ""
            for line in lines:
                s = line.strip()
                if s.startswith("■"):
                    summary = unicodedata.normalize("NFKC", s[1:].strip())[:50]
                    break
            types[type_id] = {"name": name, "summary": summary, "filepath": filepath}
        except Exception as e:
            print(f"  [WARN] {filepath.name}: {e}")
    return types


def _pick_mid_theme_from_deck(novel_type: str) -> dict:
    """
    デッキ方式で中テーマタイプを1つ事前決定する。
    ・全タイプ使い切ったらデッキをリセットして再開
    ・選択したタイプのフル内容を読み込み、S1プロンプトに注入する
    ・選択結果を output/s01_plot_twist/pre_type_{novel_type}.json に保存
    ・S9はこのファイルを参照してPass1をスキップする
    """
    deck_path     = OUTPUT_DIR / f"mid_theme_deck_{novel_type}.json"
    pre_type_path = OUTPUT_DIR / f"pre_type_{novel_type}.json"

    all_types = _load_type_names_brief()
    if not all_types:
        print("  [WARN] 中テーマタイプが読み込めません。事前決定をスキップします。")
        return {}

    all_ids = sorted(all_types.keys())

    # デッキ状態ロード
    if deck_path.exists():
        deck      = _json.loads(deck_path.read_text(encoding="utf-8"))
        remaining = deck.get("remaining", [])
        used      = deck.get("used", [])
        cycle     = deck.get("cycle", 1)
    else:
        remaining = all_ids.copy()
        used      = []
        cycle     = 1

    # 全タイプ使い切ったらリセット
    if not remaining:
        cycle += 1
        print(f"  [中テーマデッキ] 全{len(all_ids)}タイプ使用完了 → デッキリセット（サイクル{cycle}）")
        remaining = all_ids.copy()
        used      = []

    # ランダムに1つ選択
    selected_id = random.choice(remaining)
    remaining.remove(selected_id)
    used.append(selected_id)
    info = all_types[selected_id]

    # フル内容を読み込み
    type_full = info["filepath"].read_text(encoding="utf-8")
    size_kb   = len(type_full.encode("utf-8")) // 1024
    print(f"  [中テーマ事前決定] タイプ{selected_id:02d}「{info['name']}」（{size_kb}KB・残り{len(remaining)}タイプ）")

    # デッキ状態を保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    deck_path.write_text(
        _json.dumps(
            {"remaining": remaining, "used": used, "cycle": cycle,
             "last_updated": datetime.now().strftime("%Y-%m-%d")},
            ensure_ascii=False, indent=2
        ),
        encoding="utf-8"
    )

    # S9用の事前決定ファイルを保存
    pre_type_path.write_text(
        _json.dumps(
            {"type_id": selected_id, "type_name": info["name"],
             "type_summary": info["summary"],
             "timestamp": datetime.now().strftime("%Y%m%d_%H%M")},
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return {
        "type_id":   selected_id,
        "type_name": info["name"],
        "type_summary": info["summary"],
        "type_full": type_full,
    }


# ============================================================
# 上位レイヤー：価値観反転タイプ（V1〜V7）
# ============================================================

VALUE_REVERSAL_TYPES = {
    "V1": {
        "name": "善意反転",
        "desc": "救済が支配だった / 助けが搾取だった / 守ることが檻だった",
        "examples": ["保護者が支配者だった", "救済システムが搾取装置だった"],
        "question_seeds": [
            "善意と支配は何が違うのか？",
            "相手のためにした行為が相手を壊していたとき、それは愛と呼べるか？",
            "助けることと奪うことの境界線はどこにあるか？",
        ],
    },
    "V2": {
        "name": "愛情反転",
        "desc": "愛が洗脳だった / 献身が依存だった / 絆が鎖だった",
        "examples": ["愛されていたと思っていたが支配されていた", "自分の愛が相手を壊していた"],
        "question_seeds": [
            "偽物の記憶でも愛は成立するか？",
            "愛することと所有することは同じか？",
            "相手が望む自分を演じ続けた先に、本当の自分は残るか？",
        ],
    },
    "V3": {
        "name": "立場反転",
        "desc": "主人公こそ加害者だった / 被害者が共犯者だった / 敵が守護者だった",
        "examples": ["正義の側と思っていたが悪の一部だった", "被害者と思っていたが加害の連鎖の中にいた"],
        "question_seeds": [
            "加害者と被害者は入れ替わりうるか？",
            "自分が誰かを傷つけていると知らないまま正義を信じることは許されるか？",
            "善意の加害は悪意の加害より軽いか？",
        ],
    },
    "V4": {
        "name": "正義反転",
        "desc": "正義が暴力だった / 罰が贖罪を奪った / 秩序が抑圧だった",
        "examples": ["社会的正義の執行が個人の破壊だった", "罰することで被害者の癒しが閉じた"],
        "question_seeds": [
            "正しいことをしても人を傷つけるとき、それは正義か？",
            "誰かを罰することは、誰かを救うことと両立するか？",
            "秩序のために犠牲にされた個人の痛みは、誰が引き受けるか？",
        ],
    },
    "V5": {
        "name": "記憶反転",
        "desc": "偽物の記憶でも愛は成立するか / 真実が幸福を壊す / 忘却が誰かを守っていた",
        "examples": ["共有していた記憶が操作されたものだった", "忘れることで誰かを守っていた"],
        "question_seeds": [
            "偽物の記憶に基づく感情は本物か？",
            "真実を知ることと、幸福であることはどちらが大切か？",
            "記憶を奪うことは存在を奪うことか？",
        ],
    },
    "V6": {
        "name": "目的反転",
        "desc": "目的の達成が喪失だった / 手段が目的を超えた / 探していたものはすでに手の中にあった",
        "examples": ["目標を達成した瞬間に失うものがあった", "復讐を遂げた先に空虚だけが残った"],
        "question_seeds": [
            "目的を達成した後に残るものは何か？",
            "手段として使った感情が本物になるとき、何が変わるか？",
            "ずっと探していたものが最初からそばにあったとき、旅に意味はあったか？",
        ],
    },
    "V7": {
        "name": "存在反転",
        "desc": "生きることが罪だった / 消えることが愛だった / 存在が誰かを壊していた",
        "examples": ["自分が生き続けることで誰かが死んでいた", "消えることが最後の愛の表現だった"],
        "question_seeds": [
            "存在することが誰かを傷つけるとき、どう生きるべきか？",
            "消えることが愛の形になりうるか？",
            "生きていることの責任は、どこまで及ぶか？",
        ],
    },
}


# ============================================================
# 下位レイヤー：10パターン定義
# ============================================================

TWIST_DESCRIPTIONS = {
    "1:ドラドラ":  "外部の敵Aだと思ったら、別の外部の敵Bだった",
    "2:ドラウル":  "外部の敵Aだと思ったら、内部の敵Bだった",
    "3:ドラフラ":  "外部の敵Aだと思ったら、過去の罪から生まれたBだった",
    "4:ウルドラ":  "内部の敵Aだと思ったら、外部の敵Bだった",
    "5:フラドラ":  "過去の罪から生まれたAだと思ったら、外部の敵Bだった",
    "6:ウルフラ":  "内部の敵Aだと思ったら、過去の罪から生まれたBだった",
    "7:フラウル":  "過去の罪から生まれたAだと思ったら、内部の敵Bだった",
    "8:レッドラ":  "一度死んだと思った本敵が実は生きていた",
    "9:ハナサカ":  "目的は死んだと思っていたが、実は生きていた",
    "10:アオトリ": "目的は遠くにあると思ったが、実は主人公のそば（内側）にあった",
}


# ============================================================
# 価値観反転タイプ × 10パターン 重みテーブル（合計100）
# ============================================================

VALUE_TWIST_WEIGHTS = {
    "V1": {
        "1:ドラドラ":5,  "2:ドラウル":35, "3:ドラフラ":25, "4:ウルドラ":5,  "5:フラドラ":5,
        "6:ウルフラ":5,  "7:フラウル":5,  "8:レッドラ":5,  "9:ハナサカ":5,  "10:アオトリ":5,
    },
    "V2": {
        "1:ドラドラ":5,  "2:ドラウル":5,  "3:ドラフラ":5,  "4:ウルドラ":5,  "5:フラドラ":5,
        "6:ウルフラ":35, "7:フラウル":10, "8:レッドラ":5,  "9:ハナサカ":10, "10:アオトリ":15,
    },
    "V3": {
        "1:ドラドラ":25, "2:ドラウル":35, "3:ドラフラ":5,  "4:ウルドラ":15, "5:フラドラ":5,
        "6:ウルフラ":5,  "7:フラウル":5,  "8:レッドラ":5,  "9:ハナサカ":0,  "10:アオトリ":0,
    },
    "V4": {
        "1:ドラドラ":20, "2:ドラウル":5,  "3:ドラフラ":20, "4:ウルドラ":5,  "5:フラドラ":20,
        "6:ウルフラ":15, "7:フラウル":5,  "8:レッドラ":5,  "9:ハナサカ":0,  "10:アオトリ":5,
    },
    "V5": {
        "1:ドラドラ":0,  "2:ドラウル":5,  "3:ドラフラ":5,  "4:ウルドラ":15, "5:フラドラ":5,
        "6:ウルフラ":5,  "7:フラウル":5,  "8:レッドラ":5,  "9:ハナサカ":25, "10:アオトリ":30,
    },
    "V6": {
        "1:ドラドラ":5,  "2:ドラウル":5,  "3:ドラフラ":5,  "4:ウルドラ":5,  "5:フラドラ":5,
        "6:ウルフラ":5,  "7:フラウル":10, "8:レッドラ":5,  "9:ハナサカ":25, "10:アオトリ":30,
    },
    "V7": {
        "1:ドラドラ":5,  "2:ドラウル":5,  "3:ドラフラ":10, "4:ウルドラ":5,  "5:フラドラ":5,
        "6:ウルフラ":5,  "7:フラウル":30, "8:レッドラ":15, "9:ハナサカ":10, "10:アオトリ":10,
    },
}


# ============================================================
# tone_modeによるどんでん返し難易度分類
# ============================================================

# casualパターン：単純明快・即座に納得できる・前向きな読後感
CASUAL_TWIST_PATTERNS = {
    "1:ドラドラ",   # 外部の敵Aだと思ったら別の外部の敵Bだった（最もシンプル）
    "4:ウルドラ",   # 内部の敵Aだと思ったら外部の敵Bだった（誤解が解ける）
    "9:ハナサカ",   # 目的は死んだと思っていたが実は生きていた（希望系）
    "10:アオトリ",  # 目的は遠くにあると思ったが実はそばにあった（気づき系）
}

# hardパターン：道徳的に複雑・主人公が加担者・答えが出ないまま終わる
HARD_TWIST_PATTERNS = {
    "2:ドラウル",   # 外部の敵Aだと思ったら内部の敵Bだった（裏切り・重い）
    "3:ドラフラ",   # 外部の敵Aだと思ったら過去の罪から生まれたBだった（罪と罰）
    "6:ウルフラ",   # 内部の敵Aだと思ったら過去の罪から生まれたBだった（自己否定）
    "7:フラウル",   # 過去の罪Aだと思ったら内部の敵Bだった（道徳的複雑さ）
}


# ============================================================
# どんでん返し規模レベル定義
# ============================================================

TWIST_SCALE_LEVELS = {
    1: {
        "label":   "個人レベル",
        "scope":   "2者間の関係・個人的な出来事の意味が変わる範囲",
        "instruction": (
            "【規模制約 Lv1：個人レベル】\n"
            "・反転の対象は「2者間の関係」「1つの出来事の意味」「個人の目的・記憶・感情」に限定する\n"
            "・組織・社会・国家・世界規模の問題は一切登場させない\n"
            "・本当の敵（B）は個人または2〜3人の小グループを上限とする\n"
            "・封印の扉・世界の命運・大規模勢力・国家機密などは使わない\n"
            "・どんでん返し後の余韻は「2人の関係」または「主人公1人の内面」で完結させる"
        ),
    },
    2: {
        "label":   "小集団レベル",
        "scope":   "小グループ・小組織の目的・構造が変わる範囲",
        "instruction": (
            "【規模制約 Lv2：小集団レベル】\n"
            "・反転の対象は「小さな組織・チーム・コミュニティ（10人以下）」レベルまで\n"
            "・国家・大規模勢力・世界規模の仕掛けは登場させない\n"
            "・本当の敵（B）は小組織または少人数グループを上限とする\n"
            "・社会全体への影響が及ぶ展開は避ける"
        ),
    },
    3: {
        "label":   "組織レベル",
        "scope":   "中規模組織・社会の一側面が変わる範囲",
        "instruction": (
            "【規模制約 Lv3：組織レベル】\n"
            "・反転の対象は「中規模組織・社会の一側面」レベルまで\n"
            "・世界の成り立ち・世界規模の仕掛けには触れない\n"
            "・国家レベルの陰謀は可だが、世界征服・文明崩壊等は避ける"
        ),
    },
    4: {
        "label":   "世界レベル",
        "scope":   "制限なし",
        "instruction": (
            "【規模制約 Lv4：世界レベル】\n"
            "・規模の制限なし。世界・社会・文明レベルの反転も設計可"
        ),
    },
}

# 種別ラベルと最大Level対応表
_SCALE_TABLE = {
    # (novel_type, series_mode) → (max_level, label)
    ("short",  False): (1, "短編単発"),
    ("medium", False): (2, "中編単発"),
    ("short",  True):  (2, "短編シリーズ"),
    ("medium", True):  (3, "中編シリーズ"),
    ("long",   True):  (4, "長編シリーズ"),
}


def _determine_scale_level(config: dict) -> tuple:
    """
    どんでん返し規模の最大Levelと種別ラベルを返す。
    config.yaml の twist_scale_level: 1〜4 で手動固定も可。
    """
    manual = config.get("twist_scale_level", "auto")
    novel_type  = config.get("novel_type",  "short")
    series_mode = config.get("series_mode", False)

    # 手動固定
    if manual != "auto":
        try:
            lv = int(manual)
            if lv in TWIST_SCALE_LEVELS:
                label = _SCALE_TABLE.get((novel_type, bool(series_mode)), (lv, "カスタム"))[1]
                return lv, label
        except (ValueError, TypeError):
            pass

    # 長編単発は除外（エラーではなくmedium相当にフォールバック）
    if novel_type == "long" and not series_mode:
        print("  [WARN] 長編単発は除外設定です。中編単発（Lv2）として処理します。")
        return 2, "中編単発（フォールバック）"

    key = (novel_type, bool(series_mode))
    max_level, label = _SCALE_TABLE.get(key, (1, "短編単発"))
    return max_level, label


def _get_tone_mode(config: dict) -> str:
    """tone_modeを取得。short/mediumは未指定時casual、longは明示指定必須"""
    tone = config.get("tone_mode", None)
    if tone in ("casual", "hard"):
        return tone
    novel_type = config.get("novel_type", "short")
    if novel_type in ("short", "medium"):
        return "casual"
    return "hard"  # longはデフォルトhard


# ============================================================
# 3匹のモンスター理論（プロンプト用）
# ============================================================

MONSTER_THEORY = """
【3匹のモンスター理論】
・ドラキュラ：自身の外部に潜む敵（一般的な敵）
・ウルフ：自身の内部に潜む敵（二重人格・裏切り者）
・フランケンシュタインの怪物：自身の過去の罪から生まれた敵

【10パターンのどんでん返し】
敵のどんでん返し（A=偽敵、B=本敵）：
1：ドラドラ　外部の敵Aだと思ったら、別の外部の敵Bだった
2：ドラウル　外部の敵Aだと思ったら、内部の敵Bだった
3：ドラフラ　外部の敵Aだと思ったら、過去の罪から生まれたBだった
4：ウルドラ　内部の敵Aだと思ったら、外部の敵Bだった
5：フラドラ　過去の罪から生まれたAだと思ったら、外部の敵Bだった
6：ウルフラ　内部の敵Aだと思ったら、過去の罪から生まれたBだった
7：フラウル　過去の罪から生まれたAだと思ったら、内部の敵Bだった
8：レッドラ　一度死んだと思った本敵が実は生きていた
目的のどんでん返し：
9：ハナサカ　目的は死んだと思っていたが、実は生きていた
10：アオトリ　目的は遠くにあると思ったが、実は主人公のそば（内側）にあった
"""


# ============================================================
# 技法定義
# ============================================================

REVERSE_TECHNIQUES = """
【組み込む技法】

■ A：逆行型動機ミステリー（Why追求型）
通常のどんでん返しは「誰が（Who）」「どうやった（How）」を軸にするが、
「なぜそれを望むのか（Why）」を謎の核に据える。
・結末（目的・願望）を冒頭で提示し、物語を遡りながら「原因」を特定する構造
・「現在の不可解な行動」が実は「過去の純粋な動機」だったという落差を作る
・どんでん返しが「犯人特定」ではなく「意味の書き換え」として機能する

■ C：認知的盲点（信頼できない語り手）
読者が当然と思っていた前提を崩す技法。
・主人公が「自分が何かを錯覚していること」に気づいていない
・外部的要因（トラウマ・思い込み・情報操作）で認識が歪められている
・「不自然な空白」や「ノイズ」を真実の周囲に配置する
・謎解き後に世界の見え方が180度変わる「パラダイム・シフト」を設計する
"""


# ============================================================
# 抽選関数
# ============================================================

def select_value_reversal(specified: str = None, forced_twist: str = None) -> tuple:
    """価値観反転タイプを決定。
    specified   : --value-reversalで明示指定された場合はそのまま使用
    forced_twist: --twistで指定された場合、そのパターンと相性のよいVRタイプに限定して抽選
    """
    if specified and specified in VALUE_REVERSAL_TYPES:
        key = specified
        print(f"  価値観反転タイプ（指定）: {key} ── {VALUE_REVERSAL_TYPES[key]['name']}")
    else:
        candidates = list(VALUE_REVERSAL_TYPES.keys())

        # forced_twistがある場合、重みが0のVRタイプを除外
        if forced_twist:
            normalized = None
            for k in TWIST_DESCRIPTIONS:
                if k.endswith(f":{forced_twist}") or k == forced_twist:
                    normalized = k
                    break
            if normalized:
                compatible = [v for v in candidates
                              if VALUE_TWIST_WEIGHTS[v].get(normalized, 0) > 0]
                if compatible:
                    candidates = compatible
                    print(f"  [VR相性フィルタ] {forced_twist}と相性のよいVR: {candidates}")
                else:
                    print(f"  [WARN] {forced_twist}と相性のよいVRがありません。全VRから抽選します。")

        key = random.choice(candidates)
        print(f"  価値観反転タイプ（ランダム抽選）: {key} ── {VALUE_REVERSAL_TYPES[key]['name']}")
    return key, VALUE_REVERSAL_TYPES[key]


def select_twist_pattern(value_key: str, novel_type: str,
                         tone_mode: str = "casual",
                         forced: str = None) -> tuple:
    """価値観反転タイプに対応した重みで10パターンから抽選
    forced   : パターン名を直接指定（例: "ドラドラ"）→ 抽選をスキップして固定
    tone_mode: "casual" → 全10パターンから抽選 / "hard" → 複雑・重いパターンに限定
    """
    # ── forced指定あり → 抽選スキップ ─────────────────────
    if forced:
        matched = None
        for key in TWIST_DESCRIPTIONS:
            if key.endswith(f":{forced}") or key == forced:
                matched = key
                break
        if matched:
            desc = TWIST_DESCRIPTIONS[matched]
            print(f"  どんでん返しパターン（手動指定）: {matched} ── {desc}")
            return [matched], [desc]
        else:
            print(f"  [WARN] --twist '{forced}' が見つかりません。自動抽選に切り替えます。")

    # ── 自動抽選 ───────────────────────────────────────────
    weights_dict = VALUE_TWIST_WEIGHTS[value_key]

    # tone_modeによるパターン絞り込み
    if tone_mode == "hard":
        allowed = HARD_TWIST_PATTERNS
        weights_dict = {k: v for k, v in weights_dict.items() if k in allowed}
        if not weights_dict:
            weights_dict = {k: 1 for k in HARD_TWIST_PATTERNS}
        print(f"  [tone_mode] hard ── 複雑・重いパターンに限定")
    else:
        print(f"  [tone_mode] casual ── 全10パターンから抽選")

    keys = list(weights_dict.keys())
    weights = list(weights_dict.values())

    if novel_type in ["short", "medium"]:
        # 短編・中編は1パターン固定
        selected = random.choices(keys, weights=weights, k=1)[0]
        desc = TWIST_DESCRIPTIONS[selected]
        print(f"  どんでん返しパターン（1つのみ）: {selected} ── {desc}")
        return [selected], [desc]
    else:
        # 長編は最大2パターン（主+副）
        top2 = random.choices(keys, weights=weights, k=2)
        seen = []
        for t in top2:
            if t not in seen:
                seen.append(t)
        descs = [TWIST_DESCRIPTIONS[t] for t in seen]
        for t, d in zip(seen, descs):
            print(f"  どんでん返しパターン: {t} ── {d}")
        return seen, descs


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(value_key: str, value_info: dict,
                 twist_keys: list, twist_descs: list,
                 novel_type: str, tone_mode: str = "casual",
                 pre_theme: dict = None,
                 world_setting: str = "",
                 contest_division: str = "",
                 scale_level: int = 1,
                 scale_label: str = "短編単発") -> str:

    # 価値観反転の指示
    twist_count = "1つ" if novel_type in ["short", "medium"] else "最大2つ"
    twist_lines = "\n".join(
        f"  パターン{i+1}: {k} ── {d}"
        for i, (k, d) in enumerate(zip(twist_keys, twist_descs))
    )
    question_seed_lines = "\n".join(
        f"  例{i+1}: {q}" for i, q in enumerate(value_info["question_seeds"])
    )
    example_lines = "\n".join(
        f"  ・{e}" for e in value_info["examples"]
    )

    tone_instruction = (
        "【重要】tone_mode: casual\n"
        "このどんでん返しは「単発・カジュアル向け」です。\n"
        "・読者が即座に納得できるシンプルな反転を設計する\n"
        "・読後感は前向き（希望・友情・成長・再出発）を基調にする\n"
        "・道徳的に複雑な問いや、答えの出ない問いは避ける\n"
        "・主人公が加担者だった・全てが無意味だった等の結末は避ける"
    ) if tone_mode == "casual" else (
        "【重要】tone_mode: hard\n"
        "このどんでん返しは「ハード・文学的」です。\n"
        "・道徳的に複雑・主人公が加担者・答えが出ないまま終わる構造を設計する\n"
        "・読後感は重く、読者に問いかけるものにする\n"
        "・guilt / complexity / grief / ambiguity を基調にしてよい"
    )

    no_proper_nouns = """【固有名詞禁止ルール】
キャラクター名・組織名・場所名は一切確定させないこと。
以下の仮称のみ使用する：
  主人公     → 「主人公」
  相方       → 「ヒロイン」または「相方」
  偽の敵     → 「組織A」「集団A」「人物A」
  本当の敵   → 「組織B」「勢力B」「人物B」
  サブキャラ → 「人物C」「人物D」
固有名詞はS10（キャラクター設計）以降で確定される。"""

    # 世界観・部門制約セクション
    world_lines = []
    if world_setting:
        world_lines.append(f"・世界観：{world_setting}")
        world_lines.append("  → どんでん返しの設定・舞台・仕掛けは必ずこの世界観の範囲内で設計すること")
    if contest_division:
        division_notes = {
            "entertainment": "・部門：noteエンタメ部門 → 読者がスラスラ読めるテンポ感を重視。驚きと感情的な満足感を両立させること",
            "romance":       "・部門：note恋愛部門 → 感情の機微と関係性の変化を中心に設計すること",
            "mystery":       "・部門：noteミステリー部門 → 謎と解決の構造を明確に設計すること",
        }
        world_lines.append(division_notes.get(contest_division, f"・部門：{contest_division}"))

    world_section = (
        "【世界観・投稿部門の制約（必須）】\n" + "\n".join(world_lines)
    ) if world_lines else ""

    # どんでん返し規模制約セクション
    level_info    = TWIST_SCALE_LEVELS.get(scale_level, TWIST_SCALE_LEVELS[1])
    scale_section = (
        f"【どんでん返し規模制約（必須・絶対遵守）】\n"
        f"作品種別：{scale_label}  最大Level：Lv{scale_level}（{level_info['label']}）\n"
        f"対象範囲：{level_info['scope']}\n"
        f"{level_info['instruction']}\n"
    )

    # 中テーマフル内容セクション
    if pre_theme and pre_theme.get("type_full"):
        mid_theme_section = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━
【中テーマ型：設計前に必ず全文熟読すること】
タイプ{pre_theme["type_id"]:02d}「{pre_theme["type_name"]}」

{pre_theme["type_full"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
上記の中テーマ型を熟読し、この型が持つ物語の骨格・キャラクターの関係性・
感情の方向性・読後感を十分に理解した上で、以下のどんでん返し設計を行うこと。
中テーマ型との親和性を意識して設計すること。型の内容は直接言及せず、
構造に自然に織り込むこと（S9でさらに詳細設計される）。
"""
    else:
        mid_theme_section = ""

    return f"""以下の価値観反転タイプとどんでん返しパターンを組み合わせて、作品の核となる認識反転を設計してください。

{tone_instruction}

{no_proper_nouns}

{world_section}

{scale_section}

{mid_theme_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
【上位レイヤー：価値観反転タイプ（必須・変更不可）】
タイプ: {value_key} ── {value_info["name"]}
概要: {value_info["desc"]}
具体例:
{example_lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【下位レイヤー：どんでん返しパターン（{twist_count}）】
{twist_lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

{MONSTER_THEORY}

{REVERSE_TECHNIQUES}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
以下の形式で出力してください：

---

## ■ Layer 1：価値観反転の設計

**価値観反転タイプ：** {value_key} ── {value_info["name"]}

**この作品における価値観反転の核：**
（「〜と思っていたが、実は〜だった」という形で1〜2文で表現）

**反転前の世界（読者・主人公が信じていること）：**
（物語前半で提示される「正しい解釈」）

**反転後の世界（どんでん返し後の真実）：**
（どんでん返し後に明かされる「本当の構造」）

**意味の書き換え（パラダイム・シフト）：**
（謎解き後に物語全体の意味がどう変わるか）

---

## ■ Layer 2：どんでん返しパターンの実装

**選択パターン：** {twist_lines}

**偽敵（A）または偽の目的：**
（役割・読者に見せる表の顔を仮称で記述）

**本敵（B）または真の目的：**
（役割・どんでん返しで明かされる本当の姿を仮称で記述）

**どんでん返しの瞬間：**
（物語の何%地点で・どのような場面で明かされるか）

---

## ■ 技法A：逆行型動機ミステリーの設計

**冒頭で提示する「不可解な行動・目的」：**
（読者が最初に目にする謎の行動）

**遡ることで明かされる「真の動機（Why）」：**
（どんでん返し後に判明する本当の理由）

**意味の書き換え：**
（同じ行動が全く別の意味に見え直す瞬間の設計）

---

## ■ 技法C：認知的盲点の設計

**主人公の錯覚・思い込み：**
（主人公が無自覚に誤解していること）

**歪みの原因：**
（トラウマ・情報操作・思い込みなど）

**不自然な空白・ノイズ（伏線の種）：**
（真実の周囲に配置する違和感の描写例を3つ）
  1.
  2.
  3.

**パラダイム・シフトの瞬間：**
（どんでん返しで世界の見え方が180度変わる瞬間の演出）

---

## ■ S7連動：哲学的問いのドラフト

この作品の価値観反転から導かれる「問い」を3つ生成してください。
（S7で深化させるための素材として使用します）

参考となる問いの種：
{question_seed_lines}

**問い①（最も核心的な問い）：**

**問い②（登場人物の行動を問い直す問い）：**

**問い③（読後に読者の胸に残る問い）：**

---

## ■ 伏線逆算設計

価値観反転を成立させるために必要な伏線を逆算で3〜5個設計してください。

| 伏線ID | 種別 | 提示タイミング | 内容（読者には何に見えるか） | 回収時の意味 |
|-------|------|-------------|--------------------------|-----------|
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token          = config["api_keys"]["notion_token"]
    plot_db        = config["notion_dbs"].get("plot_db", "")
    novel_type     = config.get("novel_type", "short")
    specified_vr   = config.get("value_reversal", None)
    forced_twist   = config.get("twist_pattern", None)
    world_setting  = config.get("world_setting", "")
    contest_div    = config.get("contest_division", "")
    timestamp      = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S1] どんでん返し設計スキル v2 開始")
    tone_mode = _get_tone_mode(config)
    print(f"  小説タイプ: {novel_type}")
    print(f"  tone_mode: {tone_mode}")
    if world_setting:
        print(f"  世界観制約: {world_setting}")
    if contest_div:
        print(f"  部門: {contest_div}")
    if forced_twist:
        print(f"  twist指定: {forced_twist}（手動固定）")

    # ── 中テーマ事前決定（デッキ方式） ────────────────
    pre_theme = _pick_mid_theme_from_deck(novel_type)

    # ── どんでん返し規模レベル決定 ──────────────────────
    scale_level, scale_label = _determine_scale_level(config)
    print(f"  規模レベル: Lv{scale_level}（{scale_label}）")

    # ── 抽選 ──────────────────────────────────────────
    value_key, value_info = select_value_reversal(specified_vr, forced_twist)
    twist_keys, twist_descs = select_twist_pattern(value_key, novel_type, tone_mode, forced_twist)

    # ── プロンプト生成 ──────────────────────────────────
    prompt = build_prompt(
        value_key, value_info, twist_keys, twist_descs,
        novel_type, tone_mode, pre_theme,
        world_setting, contest_div,
        scale_level, scale_label
    )

    # ── Claude Sonnet で設計 ───────────────────────────
    print("  どんでん返し設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ───────────────────────────────
    pre_theme_line = (
        f"中テーマ事前決定：タイプ{pre_theme['type_id']:02d}「{pre_theme['type_name']}」"
        if pre_theme else "中テーマ事前決定：スキップ（inputディレクトリ未設定）"
    )
    content = f"""# どんでん返し設計 v2
実行日時：{timestamp}
小説タイプ：{novel_type}
価値観反転タイプ：{value_key} ── {value_info["name"]}
どんでん返しパターン：{" / ".join(twist_keys)}
どんでん返し規模：Lv{scale_level}（{scale_label}）
{pre_theme_line}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # タイムスタンプ付き（履歴保存）
    filepath = OUTPUT_DIR / f"s01_{novel_type}_{value_key}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    # 固定名 latest（S2が確実に読めるよう）
    latest_path = OUTPUT_DIR / f"s01_twist_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前": {"title": txt(f"{timestamp}_どんでん返し設計v2_{value_key}")},
            "スキル": {"rich_text": txt("S1_どんでん返し_v2")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "価値観反転": {"rich_text": txt(f"{value_key}_{value_info['name']}")},
            "ステータス": {"select": {"name": "未使用"}},
        }, "どんでん返し設計v2", result)

    print("[S1] 完了\n")
    print("  次のステップ: S2（投稿形態設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 2 --type {novel_type}")

    return {
        "value_reversal_key":  value_key,
        "value_reversal_name": value_info["name"],
        "twist_keys":          twist_keys,
        "twist_descs":         twist_descs,
        "result":              result,
        "timestamp":           timestamp,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",            default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--value-reversal",  default=None,
                        choices=["V1", "V2", "V3", "V4", "V5", "V6", "V7"],
                        help="価値観反転タイプを指定（省略時はランダム）")
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"]      = args.type
    _config["value_reversal"]  = args.value_reversal
    run(config=_config)
