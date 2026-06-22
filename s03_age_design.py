# -*- coding: utf-8 -*-
"""
S3：主人公年齢設計スキル
呼び出し：python run_pipeline.py --skill 3 --type short
役割：主人公の年齢を決定し、年齢に基づく視野・倫理・恋愛・社会圧力を設計する。
     S2の6軸パラメータ・コンテスト情報との相性チェックを行い、
     S4（年齢差設計）・S5（性別設計）へのパラメータを引き渡す。

config.yaml 対応パラメータ:
  age_range: "high-school" / "college" / "twenties" / "thirties" / "free" / 省略（AI推奨）
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

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s03_age_design"


# ============================================================
# 年齢レンジ定義（5択）
# ============================================================

AGE_RANGES = {
    "high-school": {
        "label":      "高校生",
        "age":        "15〜18歳",
        "context":    "学校・部活・放課後・受験・家族",
        "vision":     "狭い。学校・地元が世界の全て。社会の仕組みを知らない。",
        "ethics":     "正義感が強く白黒つけたがる。ルール破りへの抵抗が大きい。",
        "romance":    "初恋・片思い・告白の文化。ボディタッチに敏感。",
        "pressure":   "親・教師・受験・友人関係。同調圧力が最も強い年代。",
        "strength":   "純粋さ・勢い・感情の爆発力・成長の余白が最も大きい。",
        "weakness":   "社会経験の薄さが説得力を下げることがある。",
        "contest_fit": {
            "note":           "◎ 自分事化しやすく感情が強い",
            "kakugawa_chara": "○ 王道だが工夫が必要",
            "kakuyomu":       "◎ 王道・俺TUEEE設計と相性が良い",
            "everystory":     "◎ 感情爆発・漫画映えしやすい",
        },
    },
    "college": {
        "label":      "大学生",
        "age":        "18〜22歳",
        "context":    "サークル・バイト・一人暮らし・就活・初めての自由",
        "vision":     "広がり始める。社会を意識するが実感はまだ薄い。",
        "ethics":     "相対主義が芽生える。白黒より「グレーゾーン」を扱える。",
        "romance":    "恋愛が多様化。同棲・遠距離・三角関係が自然に成立。",
        "pressure":   "就活・親からの自立・将来への不安。自己決定が求められる。",
        "strength":   "自由と不安の共存。「大人になりきれない」葛藤が描きやすい。",
        "weakness":   "舞台設定が曖昧になりやすい。",
        "contest_fit": {
            "note":           "◎ 青春・恋愛・喪失が書きやすい",
            "kakugawa_chara": "◎ お仕事系の入り口として自然",
            "kakuyomu":       "○ 設定次第",
            "everystory":     "○ 恋愛要素と相性が良い",
        },
    },
    "twenties": {
        "label":      "20代（社会人）",
        "age":        "22〜29歳",
        "context":    "職場・上司・同僚・恋愛・仕事と私生活の両立",
        "vision":     "社会の仕組みを理解し始める。理想と現実のギャップに気づく。",
        "ethics":     "正義より「現実的な落としどころ」を探す。妥協を知っている。",
        "romance":    "結婚・同棲・別れが現実味を帯びる。傷つき方が深くなる。",
        "pressure":   "キャリア・結婚・親の老い。社会的役割への期待が増す。",
        "strength":   "リアリティと感情の深さが両立する最もドラマ的な年代。",
        "weakness":   "若年読者の感情移入がやや下がることがある。",
        "contest_fit": {
            "note":           "○ 共感しやすいが「自分事化」はやや弱め",
            "kakugawa_chara": "◎ お仕事系の王道年代",
            "kakuyomu":       "△ 設定強化が必要",
            "everystory":     "○ 社会人恋愛・復讐と相性が良い",
        },
    },
    "thirties": {
        "label":      "30代",
        "age":        "30〜39歳",
        "context":    "管理職・子育て・離婚・キャリアの岐路・親の介護",
        "vision":     "広い。社会全体を俯瞰できるが、自分の限界も見えている。",
        "ethics":     "複雑。経験から「正しさ」が相対化されている。",
        "romance":    "再婚・不倫・長年のパートナーとの倦怠。重みがある。",
        "pressure":   "社会的責任・家族・加齢。「もう若くない」という意識。",
        "strength":   "深み・複雑さ・人生の重みを描ける。",
        "weakness":   "若年層には届きにくい。コンテストでは不利なことが多い。",
        "contest_fit": {
            "note":           "△ 共感層が限られる",
            "kakugawa_chara": "○ お仕事系・人情系で強みを出せる",
            "kakuyomu":       "△ 相性が難しい",
            "everystory":     "△ コミカライズ想定には合いにくい",
        },
    },
    "free": {
        "label":      "自由（作品に最適な年齢）",
        "age":        "AIが決定",
        "context":    "S1のどんでん返しパターンとS2の6軸から最適な年齢をAIが提案",
        "vision":     "AIが設計",
        "ethics":     "AIが設計",
        "romance":    "AIが設計",
        "pressure":   "AIが設計",
        "strength":   "作品の核に最も合った年齢を選べる。",
        "weakness":   "方向性が定まっていないと散漫になる。",
        "contest_fit": {
            "note":           "AIが最適化",
            "kakugawa_chara": "AIが最適化",
            "kakuyomu":       "AIが最適化",
            "everystory":     "AIが最適化",
        },
    },
}

AGE_RANGE_ALIASES = {
    "high_school": "high-school",
    "highschool":  "high-school",
    "hs":          "high-school",
    "univ":        "college",
    "university":  "college",
    "20s":         "twenties",
    "20代":        "twenties",
    "30s":         "thirties",
    "30代":        "thirties",
}


# ============================================================
# S2出力の読み込み
# ============================================================

def load_s2_output(novel_type: str) -> tuple:
    """S2のlatestファイルとJSONパラメータを読み込む"""
    s2_dir = Path(__file__).parent.parent / "output" / "s02_submission"

    # MD（設計文書）
    md_path = s2_dir / f"s02_submission_latest_{novel_type}.md"
    md_text = ""
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")[:1500]
        print(f"  [INFO] S2出力を読み込み: {md_path.name}")

    # JSON（6軸数値）
    json_path = s2_dir / f"s02_params_latest_{novel_type}.json"
    params = {}
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            params = json.load(f)
        print(f"  [INFO] S2パラメータを読み込み: {json_path.name}")

    return md_text, params


def load_s1_output(novel_type: str) -> str:
    """S1のlatest出力を読み込む"""
    s1_dir = Path(__file__).parent.parent / "output" / "s01_plot_twist"
    latest = s1_dir / f"s01_twist_latest_{novel_type}.md"
    if latest.exists():
        return latest.read_text(encoding="utf-8")[:1500]
    return ""


# ============================================================
# コンテスト×年齢 相性チェック
# ============================================================

def check_age_contest_fit(age_key: str, contest_key: str) -> str:
    """選択した年齢とコンテストの相性を返す"""
    if not contest_key or age_key == "free":
        return ""
    age_info = AGE_RANGES.get(age_key, {})
    fit = age_info.get("contest_fit", {}).get(contest_key, "")
    label = age_info.get("label", "")
    contest_names = {
        "note":           "note創作大賞",
        "kakugawa_chara": "角川文庫キャラクター小説大賞",
        "kakuyomu":       "カクヨムコン",
        "everystory":     "エブリスタ小説大賞",
    }
    contest_name = contest_names.get(contest_key, contest_key)
    return f"【{label}×{contest_name}の相性】{fit}"


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(age_key: str, age_info: dict,
                 s1_text: str, s2_text: str, s2_params: dict,
                 contest_key: str, novel_type: str) -> str:

    weights = s2_params.get("weights", {})
    contest_name = s2_params.get("contest_name", contest_key or "未設定")

    age_fit = check_age_contest_fit(age_key, contest_key)

    # 6軸サマリー
    axes_text = ""
    if weights:
        axes_text = "【S2 6軸パラメータ】\n" + "\n".join(
            f"  {k}: {v}/100" for k, v in weights.items()
        )

    # freeモードの追加指示
    free_instruction = ""
    if age_key == "free":
        free_instruction = """
【freeモードの指示】
S1のどんでん返しパターンとS2の6軸パラメータを分析し、
この作品に最も適した主人公の年齢（具体的な数値）を提案してください。
提案理由も必ず説明してください。
"""

    return f"""あなたはこの小説作品の「主人公年齢設計者」です。
以下の情報を基に、主人公の年齢設計と年齢に基づく物語特性を設計してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【選択された年齢レンジ】
{age_info["label"]}（{age_info["age"]}）
主な生活圏：{age_info["context"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

【年齢特性（参考）】
視野：{age_info["vision"]}
倫理観：{age_info["ethics"]}
恋愛観：{age_info["romance"]}
社会圧力：{age_info["pressure"]}
強み：{age_info["strength"]}
弱み：{age_info["weakness"]}

{age_fit}

{axes_text}

【S2投稿形態設計（抜粋）】
{s2_text}

【S1どんでん返し構造（抜粋）】
{s1_text}

{free_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式で出力してください：

---

# 主人公年齢設計書（S03）

---

## ■ 主人公年齢の確定

**年齢：**（具体的な数値で記入。例：17歳）
**学年・立場：**（例：高校2年生・バイト中）
**freeモードの場合は選定理由：**

---

## ■ 年齢×どんでん返し構造の接続設計

**この年齢だからこそどんでん返しが刺さる理由：**
（S1のどんでん返しパターンと年齢特性の接続を2〜3文で）

**この年齢ならではの「歪んだ認識」：**
（S1の技法C「認知的盲点」に繋がる、年齢由来の思い込みや視野の狭さ）

---

## ■ 4軸設計（この作品固有）

### 視野の設計
**この主人公が見えていること：**
**この主人公が見えていないこと（盲点）：**
**物語を通じて視野がどう変わるか：**

### 倫理観の設計
**序盤の倫理観（単純・硬直）：**
**どんでん返し後に揺らぐ倫理観：**
**結末での倫理観の着地点：**

### 恋愛観の設計
**この年齢での恋愛の位置づけ：**
**S2の感情刺激度{weights.get("emotion", "?")}とどんでん返しパターンを踏まえた恋愛要素の比重：**
（恋愛がどんでん返しの核でない場合は「比重ゼロ／サブ要素」と明示してよい）
**恋愛が物語テーマとどう絡むか（絡まない場合はその理由）：**

### 社会圧力の設計
**主人公を縛っている社会的圧力（具体的に）：**
**その圧力が物語のどの場面で機能するか：**
**圧力から「解放」されるか「屈服」するか：**

---

## ■ コンテスト適性評価

**投稿先：** {contest_name}
**この年齢設定の適性：** {age_fit if age_fit else "（コンテスト未設定）"}
**年齢を活かした勝ち筋：**
（この年齢だからこそ可能な、コンテストで差別化できるポイント）
**年齢由来の注意点：**
（この年齢設定で陥りやすいコンテストNGパターン）

---

## ■ S4（年齢差設計）への引き渡しパラメータ

この主人公年齢を踏まえて、相方キャラクターとの年齢差設計に向けた情報：

**主人公年齢の確定値：**（数値のみ）
**物語上で自然な相方の年齢レンジ：**（例：15〜25歳）
**年齢差によって生まれやすい関係性タイプ（推奨3つ）：**
  1.
  2.
  3.
**避けるべき年齢差パターン（このコンテスト・テーマでNG）：**

---

## ■ S5（性別設計）への引き渡しパラメータ

**この年齢設定が最も活きる主人公の性別（推奨）：**
**理由：**
（S1の価値観反転・S2のコンテスト・この年齢の組み合わせから導いた根拠）
"""


# ============================================================
# メイン実行
# ============================================================

def run(config: dict = None) -> dict:
    if config is None:
        config = load_config()

    token      = config["api_keys"]["notion_token"]
    plot_db    = config["notion_dbs"].get("plot_db", "")
    novel_type = config.get("novel_type", "short")
    contest_key = config.get("contest", None)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")

    # age_range の正規化
    raw_age = config.get("age_range", "free")
    age_key = AGE_RANGE_ALIASES.get(raw_age, raw_age)
    if age_key not in AGE_RANGES:
        print(f"  [WARN] 不明なage_range: {raw_age} → freeに変更")
        age_key = "free"

    age_info = AGE_RANGES[age_key]

    print("\n[S3] 主人公年齢設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print(f"  年齢レンジ: {age_info['label']}（{age_info['age']}）")

    # ── S1/S2 出力読み込み ──────────────────
    s1_text = load_s1_output(novel_type)
    s2_text, s2_params = load_s2_output(novel_type)

    # ── 相性チェック ─────────────────────────
    fit = check_age_contest_fit(age_key, contest_key)
    if fit:
        print(f"  相性チェック: {fit}")

    # ── Claude Sonnet で設計 ────────────────
    prompt = build_prompt(
        age_key, age_info,
        s1_text, s2_text, s2_params,
        contest_key, novel_type
    )
    print("  主人公年齢設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    # ── 出力ファイル作成 ────────────────────
    content = f"""# 主人公年齢設計
実行日時：{timestamp}
小説タイプ：{novel_type}
年齢レンジ：{age_info["label"]}（{age_info["age"]}）
コンテスト：{contest_key or "未設定"}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s03_{novel_type}_{age_key}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s03_age_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    # ── Notion 保存 ────────────────────────
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_主人公年齢設計_{age_info['label']}")},
            "スキル":     {"rich_text": txt("S3_主人公年齢設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "主人公年齢設計", result)

    print("[S3] 完了\n")
    print("  次のステップ: S4（年齢差設計）")
    print(f"  コマンド例: python run_pipeline.py --skill 4 --type {novel_type}")

    return {
        "age_key":   age_key,
        "age_label": age_info["label"],
        "age_range": age_info["age"],
        "result":    result,
        "timestamp": timestamp,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    parser.add_argument("--age-range", default="free",
                        choices=["high-school", "college", "twenties",
                                 "thirties", "free"],
                        help="主人公年齢レンジ（省略時: free→AI推奨）")
    parser.add_argument("--contest", default=None,
                        choices=["note", "kakugawa_chara", "kakuyomu", "everystory"])
    args = parser.parse_args()

    _config = load_config()
    _config["novel_type"] = args.type
    _config["age_range"]  = args.age_range
    _config["contest"]    = args.contest
    run(config=_config)
