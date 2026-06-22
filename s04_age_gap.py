# -*- coding: utf-8 -*-
"""
S4：主人公と相方の年齢差設計スキル
呼び出し：python run_pipeline.py --skill 4 --type short
役割：旧hero-type7タイプを核に、権力差・経験差・保護関係・支配関係の4軸を追加設計。
     S3の主人公年齢確定値を読み込んで相方の具体的年齢を算出。
     S5（性別設計）へのパラメータを引き渡す。

config.yaml 対応パラメータ:
  hero_type: "same-age" / "older-sister" / "younger" / "cool-senior" /
             "rival" / "age-gap" / "mutual" / 省略（AI推奨）
  novel_type: "short" / "medium" / "long"
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

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s04_age_gap"


# ============================================================
# 旧hero-type 7タイプ定義（拡張版）
# ============================================================

HERO_TYPES = {
    "same-age": {
        "label":    "同年代＋精神年上",
        "age_diff": "±0〜1歳",
        "desc":     "主人公と同年代だが落ち着いており察しが良い。対等感＋憧れを同時に取れる王道。",
        "power":    "対等。どちらが上かが状況によって入れ替わる。",
        "experience": "ほぼ同等。ただし価値観・視点が異なる。",
        "protection": "相互保護。どちらが守るかが物語で揺れる。",
        "dominance":  "なし。支配関係が生まれにくいが対立が深まりやすい。",
        "drama":    "価値観の衝突・共鳴・嫉妬・競争が自然に生まれる。",
    },
    "older-sister": {
        "label":    "2〜4歳年上お姉さん",
        "age_diff": "+2〜4歳（相方が年上）",
        "desc":     "完璧そうなのに脆い。包容・癒やし・肯定を与える。孤独・自己犠牲型・甘え下手が強い。",
        "power":    "相方がやや上。経験・知識・社会的立場で先行。",
        "experience": "相方が一歩先。主人公は相方の「過去の自分」を映す鏡になる。",
        "protection": "相方→主人公の一方向が強い。ただし物語後半で逆転することで感動が生まれる。",
        "dominance":  "緩やかな保護構造。支配にはならないが依存が生まれやすい。",
        "drama":    "「脆さを隠した強者」が崩れる瞬間・主人公の成長による関係逆転。",
    },
    "younger": {
        "label":    "年下相方を守る構図",
        "age_diff": "-2〜4歳（相方が年下）",
        "desc":     "守りたい・成長を見届けたい。ただし相方側も戦う・精神的に強い必要あり。",
        "power":    "主人公がやや上。ただし精神的強さは相方が上回ることがある。",
        "experience": "主人公が先行。相方の「無知・純粋さ」が主人公の価値観を揺さぶる。",
        "protection": "主人公→相方が基本。ただし相方が主人公を精神的に救う逆転が感動を生む。",
        "dominance":  "保護が支配に転化するリスクがある。これをテーマにするとV1善意反転と直結。",
        "drama":    "成長を見守る喜び・守れなかった罪悪感・保護が支配になる恐怖。",
    },
    "cool-senior": {
        "label":    "クール年上×未熟主人公",
        "age_diff": "+3〜8歳（相方が年上）",
        "desc":     "普段感情を見せない高嶺の花が、主人公相手だけ動揺・嫉妬・不器用になるギャップ。",
        "power":    "相方が明確に上。社会的立場・実力・経験で大きく先行。",
        "experience": "相方が数年分先行。その差が主人公の「追いつきたい」動機になる。",
        "protection": "相方→主人公が強い。ただし主人公が相方の「唯一の弱点」になる逆転が核心。",
        "dominance":  "権威と依存の構造がある。意図せず支配関係になりやすい。",
        "drama":    "「完璧な人物」の崩れ方・主人公だけに見せる素の顔・追い越しの瞬間。",
    },
    "rival": {
        "label":    "同年代ライバル型",
        "age_diff": "±0〜1歳",
        "desc":     "実力拮抗・思想対立。反発→尊敬→共闘→嫉妬→恋愛を全部入れられる長編最強構造。",
        "power":    "拮抗。局面ごとに勝敗が入れ替わる。",
        "experience": "ほぼ同等だが、アプローチ・方法論が真逆。",
        "protection": "相互。互いに命を預け合う場面が最大の感情爆発になる。",
        "dominance":  "なし。支配関係が生まれた瞬間にライバル構造が崩壊する。",
        "drama":    "思想対立が深化するほど最終的な共鳴が強くなる。",
    },
    "age-gap": {
        "label":    "大きい年齢差＋精神対等",
        "age_diff": "外見大差・精神対等（10歳以上または長命種・時間差等）",
        "desc":     "長命種・時間差等で見た目年齢差あり、精神は対等。唯一無二感・孤独・死生観を描ける。",
        "power":    "表面上は年上が圧倒的上位。しかし精神・感情では対等。",
        "experience": "年上が膨大な経験を持つ。ただしその経験が「孤独の重さ」でもある。",
        "protection": "年上→年下の保護が基本。ただし「存在が互いの孤独を癒す」対等性がある。",
        "dominance":  "経験差・社会的差から支配構造が生まれやすい。これ自体をテーマにできる。",
        "drama":    "「寿命・別れ」という避けられない喪失・孤独の根源的な解消。",
    },
    "mutual": {
        "label":    "対等支援型",
        "age_diff": "±0〜3歳",
        "desc":     "互いに弱点補完・精神支援。一方的救済より互いに救い合う現代最も炎上しにくい構造。",
        "power":    "対等。得意分野が異なるため補完関係になる。",
        "experience": "異なる経験を持ち、互いから学ぶ。",
        "protection": "双方向。ピンチのタイミングが交互に訪れる設計が効果的。",
        "dominance":  "なし。これが最大の特徴で炎上しにくい。現代読者に最も受け入れられやすい。",
        "drama":    "「相手の弱さを知ったうえで選ぶ」選択の重みが感動を生む。",
    },
}

CONTEST_HERO_TYPE_FIT = {
    "note": {
        "same-age":     "◎ 共感しやすく感情線を深めやすい",
        "older-sister": "◎ 包容・癒し・喪失と相性が良い",
        "younger":      "○ 成長見届け系で感動を作れる",
        "cool-senior":  "○ ギャップ萌えで感情刺激できる",
        "rival":        "○ 思想対立から感情爆発へ",
        "age-gap":      "△ 説明が増えやすく冒頭に不向き",
        "mutual":       "◎ 現代的で自分事化しやすい",
    },
    "kakugawa_chara": {
        "same-age":     "○ 王道・安定",
        "older-sister": "◎ お姉さんキャラは角川に強い",
        "younger":      "○ 成長を見届ける構造はシリーズ化しやすい",
        "cool-senior":  "◎ 高嶺の花型は角川で実績あり",
        "rival":        "◎ シリーズ化に最適な構造",
        "age-gap":      "○ 和風・あやかし系と相性が良い",
        "mutual":       "○ バディ系として機能する",
    },
    "kakuyomu": {
        "same-age":     "○ 標準的",
        "older-sister": "○ 設定次第",
        "younger":      "◎ 守る構図は俺TUEEE感と相性が良い",
        "cool-senior":  "◎ ギャップ萌え×テンポで強い",
        "rival":        "◎ バトル・競争系と直結",
        "age-gap":      "△ テンポが落ちやすい",
        "mutual":       "○ バディ系として機能する",
    },
    "everystory": {
        "same-age":     "○ 標準的",
        "older-sister": "◎ 修羅場・感情爆発を作りやすい",
        "younger":      "◎ 漫画映えする守る構図",
        "cool-senior":  "◎ コマ映えするギャップ",
        "rival":        "◎ 対立→感情爆発→和解の漫画的構造",
        "age-gap":      "△ 設定説明が多くなりやすい",
        "mutual":       "○ 感情の対等性が女性読者に刺さる",
    },
}


# ============================================================
# S3出力の読み込み
# ============================================================

def load_s3_output(novel_type: str) -> tuple:
    """S3のlatest出力から主人公年齢を取得"""
    s3_dir = Path(__file__).parent.parent / "output" / "s03_age_design"
    latest = s3_dir / f"s03_age_latest_{novel_type}.md"
    if not latest.exists():
        print("  [INFO] S3出力なし（S4単体実行）")
        return "", 17  # デフォルト17歳

    text = latest.read_text(encoding="utf-8")
    print(f"  [INFO] S3出力を読み込み: {latest.name}")

    # 主人公年齢を抽出（「年齢：XX歳」の形式を探す）
    protagonist_age = 17
    for line in text.split("\n"):
        if "年齢：" in line or "年齢:" in line:
            import re
            m = re.search(r"(\d+)\s*歳", line)
            if m:
                protagonist_age = int(m.group(1))
                print(f"  [INFO] 主人公年齢を検出: {protagonist_age}歳")
                break

    return text[:1500], protagonist_age


def load_s2_params(novel_type: str) -> dict:
    """S2のJSONパラメータを読み込む"""
    s2_dir = Path(__file__).parent.parent / "output" / "s02_submission"
    json_path = s2_dir / f"s02_params_latest_{novel_type}.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_s1_output(novel_type: str) -> str:
    s1_dir = Path(__file__).parent.parent / "output" / "s01_plot_twist"
    latest = s1_dir / f"s01_twist_latest_{novel_type}.md"
    if latest.exists():
        return latest.read_text(encoding="utf-8")[:1500]
    return ""


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(hero_key: str, hero_info: dict,
                 protagonist_age: int,
                 s1_text: str, s3_text: str, s2_params: dict,
                 contest_key: str, twist_key: str = "") -> str:

    weights = s2_params.get("weights", {})
    contest_name = s2_params.get("contest_name", contest_key or "未設定")

    # 相方年齢の計算
    age_diff_str = hero_info["age_diff"]
    if "外見大差" in age_diff_str:
        partner_age_hint = "外見・精神的年齢は別設計（age-gap型）"
    else:
        partner_age_hint = f"主人公{protagonist_age}歳 × 年齢差{age_diff_str} → 相方は約{protagonist_age}歳の±範囲"

    # コンテスト×タイプ相性
    contest_fit = ""
    if contest_key and contest_key in CONTEST_HERO_TYPE_FIT:
        fit_dict = CONTEST_HERO_TYPE_FIT[contest_key]
        contest_fit = f"【{hero_info['label']}×{contest_name}の相性】{fit_dict.get(hero_key, '未設定')}"

    # どんでん返しパターン情報（s1_fit は廃止済み）
    twist_info = f"【S1どんでん返しパターン：{twist_key}】" if twist_key else ""

    # AI推奨モードの追加指示
    auto_instruction = ""
    if hero_key == "auto":
        auto_instruction = """
【autoモードの指示】
S1のどんでん返しパターン・S2の6軸パラメータ・S3の主人公年齢を分析し、
7タイプの中から最も適したhero-typeを1つ選んで提案してください。
選定理由も必ず説明してください。
"""

    return f"""あなたはこの小説作品の「年齢差・関係構造設計者」です。
以下の情報を基に、主人公と相方の年齢差設計を行ってください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【選択されたタイプ】
{hero_info["label"]}
年齢差：{hero_info["age_diff"]}
概要：{hero_info["desc"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【主人公年齢（S3確定値）】
{protagonist_age}歳
相方年齢の目安：{partner_age_hint}

【4軸特性（参考）】
権力差：{hero_info["power"]}
経験差：{hero_info["experience"]}
保護関係：{hero_info["protection"]}
支配関係：{hero_info["dominance"]}
生まれるドラマ：{hero_info["drama"]}

{contest_fit}
{twist_info}

【S2 6軸パラメータ】
感情刺激度: {weights.get("emotion", "?")} / キャラ魅力度: {weights.get("character", "?")}
テンポ: {weights.get("tempo", "?")} / 文学性: {weights.get("literary", "?")}

【S1どんでん返し構造（抜粋）】
{s1_text}

【S3主人公年齢設計（抜粋）】
{s3_text}

{auto_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

# 年齢差設計書（S04）

---

## ■ 年齢差の確定

**タイプ：** {hero_info["label"]}
**主人公年齢：** {protagonist_age}歳
**相方の具体的年齢：**（数値で記入）
**年齢差：**（例：+3歳、-2歳、±0歳）
**autoモードの場合は選定理由：**

---

## ■ 4軸設計（この作品固有）

### 権力差の設計
**序盤の権力構造：**（どちらが上か・その根拠）
**物語中盤での変化：**
**どんでん返し後の権力構造：**
**どんでん返し構造との接続：**（S1のどんでん返しパターンがここでどう機能するか）

### 経験差の設計
**相方が先行している経験：**（具体的に）
**主人公が先行している経験：**（具体的に）
**経験差が生む「盲点」：**（技法C認知的盲点との接続）
**経験差が埋まる瞬間：**（成長のマイルストーン）

### 保護関係の設計
**序盤の保護方向：**（A→B or 双方向）
**物語後半での逆転タイミング：**
**「守る」が物語テーマとどう絡むか：**
**保護が感動を生む場面（具体的シーン案）：**

### 支配関係の設計
**支配構造が生まれるリスクがあるか：**（あり/なし・理由）
**あり の場合：どう描くか（テーマとして扱う/回避する）：**
**S1のどんでん返し構造との接続：**（ドラドラ等のパターンと支配関係がどう絡むか）

---

## ■ 年齢差が生む感情ダイナミクス

**序盤に生まれる感情（主人公 → 相方）：**
**序盤に生まれる感情（相方 → 主人公）：**
**非対称な感情がどこで逆転・収束するか：**
**年齢差ならではの「言えない言葉」：**（この関係性でしか生まれない沈黙・遠慮）

---

## ■ コンテスト適性評価

**投稿先：** {contest_name}
**この年齢差設定の適性：** {contest_fit if contest_fit else "（コンテスト未設定）"}
**年齢差を活かした勝ち筋：**
**年齢差由来の注意点：**（陥りやすいNGパターン）

---

## ■ S5（性別設計）への引き渡しパラメータ

**確定した関係タイプ：** {hero_info["label"]}
**主人公年齢：** {protagonist_age}歳
**相方年齢：**（上記で確定した数値）
**この関係タイプで最も映える性別組み合わせ（推奨）：**
  1.
  2.
**避けるべき性別組み合わせ（このコンテスト・テーマでNG）：**
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token       = config["api_keys"]["notion_token"]
    plot_db     = config["notion_dbs"].get("plot_db", "")
    novel_type  = config.get("novel_type", "short")
    contest_key = config.get("contest", None)
    hero_key    = config.get("hero_type", "auto")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")

    # hero_typeの正規化
    if hero_key not in HERO_TYPES:
        hero_key = "auto"

    print("\n[S4] 年齢差設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")

    # ── S1/S2/S3 出力読み込み ─────────────────
    s1_text              = load_s1_output(novel_type)
    s2_params            = load_s2_params(novel_type)
    s3_text, protagonist_age = load_s3_output(novel_type)

    # ── hero_type の確定 ──────────────────────
    if hero_key == "auto":
        # autoモード：全タイプをプロンプトに渡してAIに選ばせる
        hero_info = {
            "label":    "自動選択（AIが7タイプから最適を選ぶ）",
            "age_diff": "AIが決定",
            "desc":     "S1・S2・S3の情報から最適なタイプをAIが選定します。",
            "power":    "AIが設計", "experience": "AIが設計",
            "protection": "AIが設計", "dominance": "AIが設計",
            "drama":    "AIが設計",
            "s1_fit":   {},
        }
        # 全タイプ情報をプロンプトに追加
        all_types_text = "\n【7タイプ一覧（AIが最適を選ぶ）】\n"
        for k, v in HERO_TYPES.items():
            all_types_text += f"・{k}: {v['label']}（{v['age_diff']}）── {v['desc']}\n"
        s1_text = all_types_text + "\n" + s1_text
        print(f"  hero-type: autoモード（AI推奨）")
    else:
        hero_info = HERO_TYPES[hero_key]
        print(f"  hero-type: {hero_info['label']}（{hero_info['age_diff']}）")

    # ── fix①: どんでん返しパターンをS1出力から抽出（Vタイプ廃止対応） ──
    twist_key = ""
    for line in s1_text.split("\n"):
        if "どんでん返しパターン：" in line:
            parts = line.split("：", 1)
            if len(parts) > 1:
                twist_key = parts[1].strip()
            break
    if twist_key:
        print(f"  [INFO] S1パターン: {twist_key}")

    # ── Claude Sonnet で設計 ────────────────
    prompt = build_prompt(
        hero_key, hero_info, protagonist_age,
        s1_text, s3_text, s2_params,
        contest_key, twist_key
    )
    print("  年齢差設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    content = f"""# 年齢差設計
実行日時：{timestamp}
小説タイプ：{novel_type}
hero-type：{hero_key}（{hero_info["label"]}）
主人公年齢：{protagonist_age}歳
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s04_{novel_type}_{hero_key}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s04_age_gap_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_年齢差設計_{hero_info['label']}")},
            "スキル":     {"rich_text": txt("S4_年齢差設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "年齢差設計", result)

    print("[S4] 完了\n")
    print("  次のステップ: S5（性別設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 5 --type {novel_type}")

    return {
        "hero_key":        hero_key,
        "hero_label":      hero_info["label"],
        "protagonist_age": protagonist_age,
        "result":          result,
        "timestamp":       timestamp,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--hero-type", default="auto",
                        choices=["same-age", "older-sister", "younger",
                                 "cool-senior", "rival", "age-gap", "mutual", "auto"],
                        help="相方タイプ（省略時: auto→AI推奨）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"] = args.type
    _config["hero_type"]  = args.hero_type
    _config["contest"]    = args.contest
    run(config=_config)
