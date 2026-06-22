# -*- coding: utf-8 -*-
"""
S2：投稿形態設計スキル
呼び出し：python run_pipeline.py --skill 2 --type short
役割：投稿媒体・コンテスト適性を6軸重みパラメータで設計し、
     後続スキル（S7〜S24）が参照する方針ファイルを出力する。
     「受かりそうな作品」に寄せすぎず、作品の本質を守る設計思想。

config.yaml 対応パラメータ:
  contest: "note" / "kakugawa_chara" / "kakuyomu" / "everystory" / 省略（手動入力）
  
  コンテスト未指定時（手動入力モード）:
    weight_emotion:    0〜100  感情刺激度
    weight_character:  0〜100  キャラ魅力度
    weight_tempo:      0〜100  テンポ
    weight_visual:     0〜100  視覚性
    weight_literary:   0〜100  文学性
    weight_commercial: 0〜100  市場性
"""

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s02_submission"


# ============================================================
# コンテスト定義
# ============================================================

CONTEST_PROFILES = {
    "note": {
        "name":        "note創作大賞",
        "organizer":   "note株式会社",
        "period":      "例年4〜7月募集／秋〜冬結果発表",
        "point":       "最重要は「冒頭3行」。感情・事件・違和感から始まる",
        "weights": {
            "emotion":    90,
            "character":  60,
            "tempo":      70,
            "visual":     50,
            "literary":   30,
            "commercial": 60,
        },
        "must_include": [
            "感情が強い（泣ける・喪失・再生・罪悪感）",
            "一話が短く読みやすい（1500〜2000文字目安）",
            "タイトルが気になる",
            "人間関係が濃い（2〜3人を深く）",
            "感情の核（泣ける・喪失・再生・罪悪感）を早期から明示すること",
            "現代舞台",
            "自分事化しやすいテーマ",
            "冒頭3行：感情・事件・違和感のいずれかで開始",
        ],
        "must_exclude": [
            "冒頭での世界観・設定説明",
            "設定重視・導入が遅い",
            "難解な文章・重厚SF",
            "純文学寄り・哲学的すぎる",
            "キャラが弱い・一話が長い",
        ],
        "forbidden_zone": {
            "literary":   (">=", 70),
            "tempo":      ("<=", 40),
        },
    },

    "kakugawa_chara": {
        "name":        "角川文庫キャラクター小説大賞",
        "organizer":   "角川文庫キャラクター文芸編集部",
        "period":      "例年5〜8月募集／秋〜冬選考",
        "point":       "「キャラで読ませる」。推したくなる主人公＋シリーズ化できるキャラ設計",
        "weights": {
            "emotion":    60,
            "character":  90,
            "tempo":      60,
            "visual":     50,
            "literary":   40,
            "commercial": 80,
        },
        "must_include": [
            "主人公が魅力的で推したくなる",
            "バディ・居場所系・お仕事ものの関係性",
            "日常＋事件の構造",
            "和風・あやかし・ライトミステリの要素（いずれか）",
            "続刊できるシリーズ設計",
            "人情・温かみのある人間関係",
        ],
        "must_exclude": [
            "世界設定偏重・ハードSF",
            "暗すぎる・主人公が地味",
            "文章実験系・難解",
            "キャラ数過多・バトル偏重",
        ],
        "forbidden_zone": {
            "literary":   (">=", 70),
            "character":  ("<=", 40),
        },
    },

    "kakuyomu": {
        "name":        "カクヨムコン",
        "organizer":   "KADOKAWA",
        "period":      "例年12月〜2月応募／春〜初夏結果発表",
        "point":       "第一話が超重要。冒頭で快感を出せる作品。連載力が問われる",
        "weights": {
            "emotion":    70,
            "character":  80,
            "tempo":      90,
            "visual":     60,
            "literary":   20,
            "commercial": 70,
        },
        "must_include": [
            "第一話に強いフック・引き",
            "毎話フックがある連載設計",
            "キャラが立っている・テンポが速い",
            "会話が多い・ジャンル明快",
            "異世界・恋愛要素",
            "「俺TUEEE」的な快感設計",
        ],
        "must_exclude": [
            "説明から始まる・地の文が重い",
            "展開が遅い・山場がない",
            "一話が長すぎる・ジャンル不明",
            "純文学系・暗すぎる・主人公が弱い",
        ],
        "forbidden_zone": {
            "tempo":    ("<=", 50),
            "literary": (">=", 60),
        },
    },

    "everystory": {
        "name":        "エブリスタ小説大賞",
        "organizer":   "エブリスタ",
        "period":      "年間通して複数開催",
        "point":       "コミカライズ前提。映像が浮かぶ作品。文章力より商業化しやすさ",
        "weights": {
            "emotion":    90,
            "character":  70,
            "tempo":      90,
            "visual":     90,
            "literary":   10,
            "commercial": 90,
        },
        "must_include": [
            "漫画映え・コマになる感情爆発シーン",
            "修羅場・SNS映えする展開",
            "強いヒロイン・恋愛要素・復讐要素",
            "会話中心・ビジュアルが浮かぶ描写",
            "短文テンポ・コミカライズ前提の商業設計",
        ],
        "must_exclude": [
            "内面描写だけ・静かな文学",
            "地味・展開が穏やかすぎる",
            "設定説明多い・男性向け硬派SF",
            "哲学寄り・長い独白",
        ],
        "forbidden_zone": {
            "literary": (">=", 50),
            "tempo":    ("<=", 50),
        },
    },
}

AXIS_LABELS = {
    "emotion":    "感情刺激度",
    "character":  "キャラ魅力度",
    "tempo":      "テンポ",
    "visual":     "視覚性",
    "literary":   "文学性",
    "commercial": "市場性",
}

AXIS_DESC = {
    "emotion":    "泣ける・感情爆発・喪失・再生の強度",
    "character":  "主人公の魅力・推したくなる度・キャラの立ち方",
    "tempo":      "展開速度・会話比率・一話の短さ・引きの強さ",
    "visual":     "漫画映え・ビジュアルが浮かぶ・SNS映え・コマ映え",
    "literary":   "哲学性・余白・内面描写の深さ・文体の実験性",
    "commercial": "商業化しやすさ・続刊性・シリーズ化・市場適合度",
}


# ============================================================
# 禁止ゾーン判定
# ============================================================

def check_forbidden_zones(weights: dict, forbidden: dict) -> list:
    """禁止ゾーンに入っている軸を検出して警告リストを返す"""
    warnings = []
    for axis, (op, threshold) in forbidden.items():
        val = weights.get(axis, 0)
        label = AXIS_LABELS[axis]
        if op == ">=" and val >= threshold:
            warnings.append(
                f"⚠️ {label}が{val}（禁止ゾーン：{threshold}以上）"
                f" → このコンテストでは{label}を下げることを推奨"
            )
        elif op == "<=" and val <= threshold:
            warnings.append(
                f"⚠️ {label}が{val}（禁止ゾーン：{threshold}以下）"
                f" → このコンテストでは{label}を上げることを推奨"
            )
    return warnings


# ============================================================
# S1どんでん返しパターンとの整合性チェック（fix②: Vタイプ廃止対応）
# ============================================================

def check_twist_compatibility(twist_key: str, weights: dict,
                               contest_key: str) -> list:
    """どんでん返しパターンと6軸・コンテストの整合性を確認し、注意点を返す"""
    notes = []
    if not twist_key:
        return notes

    # パターン別の注意事項
    if "ドラドラ" in twist_key:
        if weights.get("character", 0) < 50:
            notes.append(
                f"📌 ドラドラは偽敵Aへの感情移入が必須です。"
                f"キャラ魅力度{weights['character']}は低めです。"
                f"偽敵Aの印象付けを冒頭30%以内に集中させてください。"
            )
    elif "ドラウル" in twist_key:
        if weights.get("emotion", 0) < 60:
            notes.append(
                f"📌 ドラウル（内部の裏切り者）は感情的打撃が核です。"
                f"感情刺激度{weights['emotion']}を意識した設計にしてください。"
            )
    elif "ドラフラ" in twist_key or "ウルフラ" in twist_key:
        if weights.get("literary", 0) < 25:
            notes.append(
                f"📌 このパターンは罪の意識・自己認識の反転が深みの源泉です。"
                f"文学性{weights['literary']}が低いと内省が浅くなります。"
                f"S21余白設計で補完してください。"
            )
    elif "アオトリ" in twist_key:
        if weights.get("literary", 0) < 30:
            notes.append(
                f"📌 アオトリ（目的は内側に）は気づきの余白が命です。"
                f"文学性{weights['literary']}が低いと反転が伝わりにくくなります。"
                f"S21余白設計で補完してください。"
            )
        if weights.get("tempo", 0) > 80:
            notes.append(
                f"📌 アオトリはゆっくりした気づきの積み上げが必要です。"
                f"テンポ{weights['tempo']}が速すぎると反転前の印象が定着しません。"
            )
    elif "ハナサカ" in twist_key:
        if weights.get("literary", 0) < 30:
            notes.append(
                f"📌 ハナサカ（目的は生きていた）は感情の蓄積と余韻が重要です。"
                f"文学性{weights['literary']}が低いと感動が薄くなります。"
                f"S21余白設計で補完してください。"
            )

    # コンテスト×パターンの特殊な組み合わせ
    if contest_key == "kakuyomu" and any(p in twist_key for p in ["ハナサカ", "アオトリ"]):
        notes.append(
            f"📌 カクヨム×{twist_key}はテンポ重視のプラットフォームと相性がやや難しい組み合わせです。"
            f"各話末の引きを強め、目的反転前に読者を引き止める設計にしてください。"
        )
    if contest_key == "everystory" and any(p in twist_key for p in ["ドラフラ", "ウルフラ", "フラウル"]):
        notes.append(
            f"📌 エブリスタ×{twist_key}は哲学的内省が中心になりがちです。"
            f"罪悪感を「感情爆発の瞬間」に溶け込ませる形で表現してください。"
        )

    return notes


# ============================================================
# 求める作品像（vision.md）の読み込み
# ============================================================

def load_vision(base_dir: Path = None) -> str:
    """input/vision.md を読み込む（なければ空文字）"""
    if base_dir is None:
        base_dir = Path(__file__).parent.parent
    vision_path = base_dir / "input" / "vision.md"
    if not vision_path.exists():
        return ""
    text = vision_path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    print(f"  [OK] vision.md 読み込み済み（{len(text)}字）")
    return text

def load_s1_output(novel_type: str) -> str:
    """S1のlatest出力を読み込む"""
    s1_dir = Path(__file__).parent.parent / "output" / "s01_plot_twist"
    latest = s1_dir / f"s01_twist_latest_{novel_type}.md"
    if latest.exists():
        print(f"  [INFO] S1出力を読み込み: {latest.name}")
        return latest.read_text(encoding="utf-8")[:2000]
    print("  [INFO] S1出力なし（S2単体実行）")
    return ""


def check_s1_compatibility(value_reversal_key: str, weights: dict,
                           contest_key: str) -> list:
    """価値観反転タイプと6軸の整合性を確認し、注意点を返す"""
    notes = []

    # V5（記憶反転）・V7（存在反転）は文学性が低すぎると価値観反転が機能しにくい
    if value_reversal_key in ["V5", "V7"] and weights.get("literary", 0) < 30:
        notes.append(
            f"📌 価値観反転タイプ{value_reversal_key}は哲学的余韻が重要です。"
            f"文学性{weights['literary']}は低めですが、"
            f"「余白」だけは意図的に守ってください（S21余白設計で補完）。"
        )

    # V3（立場反転）はキャラ魅力度が低いと反転が伝わりにくい
    if value_reversal_key == "V3" and weights.get("character", 0) < 50:
        notes.append(
            f"📌 価値観反転タイプV3（立場反転）はキャラへの感情移入が必須です。"
            f"キャラ魅力度{weights['character']}を意識して設計してください。"
        )

    # エブリスタ × V5/V7 は哲学性が禁止ゾーンに近い
    if contest_key == "everystory" and value_reversal_key in ["V5", "V7"]:
        notes.append(
            f"📌 エブリスタ×{value_reversal_key}は相性がやや難しい組み合わせです。"
            f"哲学的な問いは「感情爆発の瞬間」に溶け込ませる形で表現してください。"
        )

    return notes


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(contest_key: str, contest_info: dict,
                 weights: dict, s1_text: str,
                 forbidden_warnings: list, compat_notes: list,
                 vision_text: str = "", twist_key: str = "",
                 world_setting: str = "", contest_division: str = "",
                 character_count: int = 0, character_count_max: int = 0) -> str:

    # fix②: f-string 内で使うパターン表示ラベル
    twist_key_label = twist_key if twist_key else "未設計"

    axes_text = "\n".join(
        f"  {AXIS_LABELS[k]}（{AXIS_DESC[k]}）: {weights[k]}/100"
        for k in ["emotion", "character", "tempo", "visual", "literary", "commercial"]
    )

    must_include = "\n".join(f"  ✅ {item}" for item in contest_info["must_include"])
    must_exclude = "\n".join(f"  ❌ {item}" for item in contest_info["must_exclude"])

    warnings_text = (
        "\n".join(f"  {w}" for w in forbidden_warnings)
        if forbidden_warnings else "  なし"
    )
    compat_text = (
        "\n".join(f"  {n}" for n in compat_notes)
        if compat_notes else "  なし"
    )

    # fix③: S1パターン名を明示した構造化セクション
    if twist_key and s1_text:
        s1_section = (
            f"\n【S1どんでん返し設計情報】\n"
            f"選択パターン：{twist_key}\n"
            f"上記パターンで設計された偽敵A・本敵B・伏線・感情着地点が以下の設計書にあります。\n"
            f"後続スキルへの指示はこのパターンと整合するよう設計してください。\n"
            f"設計書（概要）：\n{s1_text[:1500]}\n"
        )
    elif s1_text:
        s1_section = f"\n【S1どんでん返し設計情報】\n{s1_text}\n"
    else:
        s1_section = ""

    # vision.md：親和性の高い要素だけを参考情報として注入
    vision_section = (
        f"\n【求める作品像（参考・親和性の高い要素を採用）】\n{vision_text}\n"
        f"※上記は出版社・コンテスト側の募集要項です。この作品のトーン・テーマと"
        f"親和性の高い要素のみを後続設計に取り込んでください。\n"
        if vision_text else ""
    )

    # 世界観制約セクション
    world_lines = []
    if world_setting:
        world_lines.append(f"・世界観制約：{world_setting}")
        world_lines.append("・「現代舞台」要件との整合：ファンタジー要素は現代日常の延長として自然に存在させる")
        world_lines.append("・冒頭での世界観説明は禁止（must_exclude準拠）。ファンタジー要素は行動・事件の中で自然に提示する")
    if contest_division:
        div_map = {
            "entertainment": "・部門：noteエンタメ部門 → テンポ・驚き・感情的満足を最優先",
            "romance":        "・部門：note恋愛部門 → 感情の機微と関係性変化を最優先",
            "mystery":        "・部門：noteミステリー部門 → 謎と解決の構造を最優先",
        }
        world_lines.append(div_map.get(contest_division, f"・部門：{contest_division}"))
    world_section = (
        "\n【世界観・部門制約（後続スキルへの指針に必ず反映）】\n"
        + "\n".join(world_lines) + "\n"
    ) if world_lines else ""

    # 登場人物数制約セクション
    if character_count > 0:
        character_section = (
            f"\n【登場人物数制約（全スキル共通・絶対遵守）】\n"
            f"・推奨人数：{character_count}名\n"
            f"・上限人数：{character_count_max}名（これを超えるキャラクターは設計しない）\n"
            f"・人数は少ないほど関係性の密度が高まる。上限は緊急時のみ使用する\n"
        )
    else:
        character_section = ""

    return f"""あなたはこの小説作品の「投稿形態設計者」です。
以下の情報を基に、作品の投稿方針と後続スキルへの指針を設計してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【投稿先コンテスト】
名称：{contest_info["name"]}
主催：{contest_info["organizer"]}
開催時期：{contest_info["period"]}
重要ポイント：{contest_info["point"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【6軸重みパラメータ】
{axes_text}

【必ず盛り込む要素】
{must_include}

【必ず排除する要素】
{must_exclude}

【禁止ゾーン警告】
{warnings_text}

【S1どんでん返しパターンとの整合性注意（パターン：{twist_key_label}）】
{compat_text}
{s1_section}{vision_section}{world_section}{character_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

重要思想：
・「受かりそうな作品」に寄せすぎない
・作品の核（価値観反転・哲学的問い）は守る
・媒体適性は「表現の方法」で対応する（内容を歪めない）

以下の形式で出力してください：

---

# 投稿形態設計書（S02）

---

## ■ 投稿形態サマリー

**投稿先：** {contest_info["name"]}
**この作品が目指すポジション：**
（6軸のバランスから読み取れる「この作品はどういう作品として勝負するか」を1〜2文で）

**強みとして打ち出す軸：**
（最も高い軸2つを活かした勝ち筋を説明）

**意図的に抑える軸：**
（低い軸をどう扱うか。完全に排除するか、別の軸で補完するか）

---

## ■ 後続スキルへの方針指示

### S7（哲学的問い設計）への指示
（この重みで哲学的問いをどう扱うか。深く掘るか・感情に溶け込ませるか）

### S8（感情設計）への指示
（感情刺激度{weights['emotion']}を踏まえた読後感の方向性）

### S10〜S13（キャラクター設計）への指示
（キャラ魅力度{weights['character']}を踏まえた主人公・相方の設計方針）

### S14（全体プロット設計）への指示
（テンポ{weights['tempo']}・市場性{weights['commercial']}を踏まえた構造方針）

### S21（余白設計）への指示
（文学性{weights['literary']}を踏まえた「説明しない・回収しない」の度合い）

### S24（初版文章生成）への指示
（視覚性{weights['visual']}を踏まえた文章スタイルの方針）

### S30（既視感除去）への指示
（このコンテストで「ありがちな型」として排除すべきパターン）

---

## ■ 禁止事項リスト（全スキル共通）

このコンテストでNGとなる表現・構造を具体的に列挙してください。
後続スキルが参照する「絶対に書かないこと」リストです。

| # | 禁止事項 | 理由 |
|---|---------|------|

---

## ■ 冒頭設計の指針

このコンテストの「冒頭ルール」を踏まえた具体的な書き出し設計：

**第1文のタイプ：**（感情型 / 事件型 / 違和感型 / 快感型 のどれか）
**第1文に必ず入れる要素：**
**第1文で絶対に避ける要素：**
**冒頭3行で読者に感じさせること：**

---

## ■ 平均化回避チェック

この作品が「AI生成あるある」の平均的作品に埋没しないための指針：

**このコンテストで量産されがちな型：**
（3つ列挙）

**この作品が差別化できるポイント：**
（S1のどんでん返しパターン「{twist_key_label}」を踏まえた、この作品固有の強み）
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token         = config["api_keys"]["notion_token"]
    plot_db       = config["notion_dbs"].get("plot_db", "")
    novel_type    = config.get("novel_type", "short")
    contest_key   = config.get("contest", None)
    timestamp     = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S2] 投稿形態設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    # ── コンテスト選択 or 手動入力 ──────────────
    if contest_key and contest_key in CONTEST_PROFILES:
        contest_info = CONTEST_PROFILES[contest_key]
        weights = contest_info["weights"].copy()
        print(f"  コンテスト: {contest_info['name']}")
        print("  重みパラメータ（コンテスト自動設定）:")
    else:
        # 手動入力モード
        contest_key = "manual"
        contest_info = {
            "name":        config.get("contest_name", "（未指定）"),
            "organizer":   config.get("contest_organizer", "（未指定）"),
            "period":      config.get("contest_period", "（未指定）"),
            "point":       config.get("contest_point", "作品の本質を最優先に設計する"),
            "must_include": config.get("must_include", ["作品の核となる価値観反転を最優先"]),
            "must_exclude": config.get("must_exclude", ["AI臭・平均化・既視感"]),
            "forbidden_zone": {},
        }
        weights = {
            "emotion":    int(config.get("weight_emotion",    70)),
            "character":  int(config.get("weight_character",  70)),
            "tempo":      int(config.get("weight_tempo",      60)),
            "visual":     int(config.get("weight_visual",     60)),
            "literary":   int(config.get("weight_literary",   50)),
            "commercial": int(config.get("weight_commercial", 50)),
        }
        print(f"  コンテスト: 手動入力モード（{contest_info['name']}）")
        print("  重みパラメータ（config.yaml から読み込み）:")

    for k in ["emotion", "character", "tempo", "visual", "literary", "commercial"]:
        print(f"    {AXIS_LABELS[k]}: {weights[k]}/100")

    # ── 禁止ゾーンチェック ───────────────────────
    forbidden = contest_info.get("forbidden_zone", {})
    forbidden_warnings = check_forbidden_zones(weights, forbidden)
    if forbidden_warnings:
        print("  [WARNING] 禁止ゾーン検出:")
        for w in forbidden_warnings:
            print(f"    {w}")

    # ── S1出力の読み込み ────────────────────────
    s1_text = load_s1_output(novel_type)

    # fix②③: S1出力からどんでん返しパターンを抽出（Vタイプではなくパターン名）
    twist_key = ""
    for line in s1_text.split("\n"):
        if "どんでん返しパターン：" in line:
            parts = line.split("：", 1)
            if len(parts) > 1:
                twist_key = parts[1].strip()
            break
    if twist_key:
        print(f"  [INFO] S1パターン: {twist_key}")
    else:
        print("  [INFO] S1パターン: 未検出（S2単体実行）")

    # ── S1パターンとの整合性チェック ─────────────────
    compat_notes = check_twist_compatibility(twist_key, weights, contest_key)
    if compat_notes:
        print("  [INFO] S1整合性注意:")
        for n in compat_notes:
            print(f"    {n}")

    # fix①: vision.md を読み込んで build_prompt に渡す
    vision_text     = load_vision()
    world_setting   = config.get("world_setting", "")
    contest_div     = config.get("contest_division", "")
    char_count      = config.get("character_count", 0)
    char_count_max  = config.get("character_count_max", 0)
    if world_setting:
        print(f"  世界観制約: {world_setting}")
    if contest_div:
        print(f"  部門: {contest_div}")
    if char_count:
        print(f"  登場人物数: 推奨{char_count}名 / 上限{char_count_max}名")

    # ── Claude Sonnet で設計 ────────────────────
    prompt = build_prompt(
        contest_key, contest_info, weights,
        s1_text, forbidden_warnings, compat_notes,
        vision_text=vision_text, twist_key=twist_key,
        world_setting=world_setting, contest_division=contest_div,
        character_count=char_count, character_count_max=char_count_max
    )
    print("  投稿形態設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────────
    axes_summary = " / ".join(
        f"{AXIS_LABELS[k]}:{weights[k]}"
        for k in ["emotion", "character", "tempo", "visual", "literary", "commercial"]
    )
    content = f"""# 投稿形態設計
実行日時：{timestamp}
小説タイプ：{novel_type}
投稿先：{contest_info["name"]}
6軸パラメータ：{axes_summary}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # タイムスタンプ付き（履歴）
    filepath = OUTPUT_DIR / f"s02_{novel_type}_{contest_key}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    # 固定名 latest（後続スキル参照用）
    latest_md = OUTPUT_DIR / f"s02_submission_latest_{novel_type}.md"
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest MD: {latest_md.name}")

    # 6軸パラメータをJSONで保存（後続スキルが数値で参照）
    params = {
        "contest":      contest_key,
        "contest_name": contest_info["name"],
        "novel_type":   novel_type,
        "timestamp":    timestamp,
        "weights":      weights,
        "forbidden_warnings": forbidden_warnings,
        "compat_notes": compat_notes,
    }
    latest_json = OUTPUT_DIR / f"s02_params_latest_{novel_type}.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    print(f"  [OK] Latest JSON: {latest_json.name}")

    # ── Notion 保存 ────────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_投稿形態設計_{contest_info['name']}")},
            "スキル":     {"rich_text": txt("S2_投稿形態設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "投稿先":     {"rich_text": txt(contest_info["name"])},
            "ステータス": {"select": {"name": "未使用"}},
        }, "投稿形態設計", result)

    print("[S2] 完了\n")
    print("  次のステップ: S3（主人公年齢設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 3 --type {novel_type}")

    return {
        "contest_key":  contest_key,
        "contest_name": contest_info["name"],
        "weights":      weights,
        "result":       result,
        "timestamp":    timestamp,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",    default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--contest", default=None,
                        choices=list(CONTEST_PROFILES.keys()),
                        help="コンテスト指定（省略時は手動入力モード）")
    # 手動入力モード用オプション
    parser.add_argument("--weight-emotion",    type=int, default=70)
    parser.add_argument("--weight-character",  type=int, default=70)
    parser.add_argument("--weight-tempo",      type=int, default=60)
    parser.add_argument("--weight-visual",     type=int, default=60)
    parser.add_argument("--weight-literary",   type=int, default=50)
    parser.add_argument("--weight-commercial", type=int, default=50)
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"]         = args.type
    _config["contest"]            = args.contest
    _config["weight_emotion"]     = args.weight_emotion
    _config["weight_character"]   = args.weight_character
    _config["weight_tempo"]       = args.weight_tempo
    _config["weight_visual"]      = args.weight_visual
    _config["weight_literary"]    = args.weight_literary
    _config["weight_commercial"]  = args.weight_commercial
    run(config=_config)
