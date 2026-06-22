# -*- coding: utf-8 -*-
"""
S23：シーン別プロット設計スキル
呼び出し：python run_pipeline.py --skill 23 --type short
役割：S19〜S22の全設計を統合し、各シーンの5レイヤー設計を行う。
     5レイヤー：行動 / 感情 / 思考 / カメラワーク / 音響
     これが初版文章生成（S24）の直接の設計書になる。

重要思想：
  シーン設計は「何が起きるか」だけでなく
  「どう見えるか・何を感じるか・何が聞こえるか」まで設計する

次ステップ：S24（初版文章生成）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import (
    load_config, call_claude_sonnet,
    notion_create_page_long, txt
)
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s23_scene_plot"


# ============================================================
# 5レイヤー定義
# ============================================================

FIVE_LAYERS = """
【5レイヤー設計の定義】

■ Layer 1：行動（Action）
  何が起きるか。誰が・何を・どこで・どう行動するか。
  客観的な事実として設計する。

■ Layer 2：感情（Emotion）
  登場人物が感じていること。ただし直接書かない。
  「悲しい」ではなく「手が震えている」という設計をする。

■ Layer 3：思考（Thought）
  登場人物が考えていること・内的独白の方向性。
  ただし最小限にする。行動で示せるなら思考は不要。

■ Layer 4：カメラワーク（Camera）
  視点・距離感・アングル・切り替えを設計する。
  富野由悠季「映像の原則」を参考に。
  例：俯瞰→クローズアップ→主観視点

■ Layer 5：音響（Sound）
  聞こえる音・沈黙・環境音・心音を設計する。
  感情を強化する音の設計。
  例：雨音が止む瞬間・心臓の音だけが聞こえる沈黙
"""


# ============================================================
# 前ステップ出力の読み込み
# ============================================================

def load_prev_outputs(novel_type: str) -> dict:
    base = Path(__file__).parent.parent / "output"
    results = {}

    paths = {
        "s19": base / "s19_act_structure" / f"s19_act_latest_{novel_type}.md",
        "s21": base / "s21_margin"        / f"s21_margin_latest_{novel_type}.md",
        "s22": base / "s22_scene_emotion" / f"s22_emotion_latest_{novel_type}.md",
    }
    limits = {"s19": 1500, "s21": 1500, "s22": 1500}

    for key, path in paths.items():
        if path.exists():
            results[key] = path.read_text(encoding="utf-8")[:limits[key]]
            print(f"  [INFO] {key.upper()}出力: 読み込み済み")
        else:
            results[key] = ""

    # S10キャラクター設計も読み込む（口調・行動パターン参照用）
    s10 = base / "s10_character" / f"s10_character_latest_{novel_type}.md"
    results["s10"] = s10.read_text(encoding="utf-8")[:3000] if s10.exists() else ""
    if results["s10"]:
        print(f"  [INFO] S10出力: 読み込み済み")

    return results


# ============================================================
# プロンプト構築
# ============================================================

def build_prompt(prev: dict, novel_type: str,
                 world_setting: str = "", setting_confirmed: dict = None) -> str:

    world_lines = []
    if world_setting:
        world_lines.append(f"・世界観：{world_setting}")
    if setting_confirmed:
        for k, v in setting_confirmed.items():
            world_lines.append(f"・{v}")
    world_section = (
        "【確定済み世界観・設定（全シーンに反映）】\n"
        + "\n".join(world_lines) + "\n"
    ) if world_lines else ""

    return f"""あなたはこの小説作品の「シーン設計者」です。
S19〜S22の全設計を統合し、各シーンの5レイヤー設計を行ってください。
これがS24（初版文章生成）の直接の設計書になります。
{world_section}

{FIVE_LAYERS}

重要思想：
・Layer 2（感情）は「直接書かない」設計にする
・Layer 3（思考）は最小限。行動で示せる場合は省略
・Layer 4（カメラ）はS24での文章視点の指示になる
・Layer 5（音響）は感情を強化する重要な演出装置
・余白（S21）のある場面はLayer 2〜3を意図的に薄くする

━━━━━━━━━━━━━━━━━━━━━━━━━━━
【S19 起承転結設計（章の役割・感情強度）】
{prev["s19"]}

【S22 シーン別感情設計（S23引き渡しパラメータ含む）】
{prev.get("s22_table") or prev["s22"]}

【S21 余白マップ（場面別余白ID一覧）】
{prev.get("s21_map") or prev["s21"]}

【S10 キャラクター設計（行動パターン・口癖）】
{prev["s10"]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

# シーン別プロット設計書（S23）

---

全章のシーンを以下の形式で設計してください。
各章に2〜3シーン。章末シーンは必ず「次章への引き」を持つ。

---

## ■ プロローグ

### Sc-P1（プロローグ Scene 1）
**【行動】** 何が起きるか：
**【感情】** 登場人物の感情（直接書かず→行動・身体で示す方法）：
**【思考】** 内的独白の方向性（必要最小限）：
**【カメラ】** 視点・距離・アングル：
**【音響】** 聞こえる音・沈黙：
**余白：** あり / なし（ある場合は種別）
**フック：** （次を読ませる引き）

---

## ■ 第1章

### Sc-1-1（第1章 Scene 1）
**【行動】**：
**【感情】**：
**【思考】**：
**【カメラ】**：
**【音響】**：
**余白：**
**フック：**

### Sc-1-2（第1章 Scene 2）
（同形式）

### Sc-1-3（第1章 Scene 3・非日常突入）
（同形式）
**章末フック：**（強制）次章への強い引き

---

## ■ 第2〜3章

### Sc-2-1 〜 Sc-3-2
（各シーン同形式・2〜3シーンずつ）
**章末フック：**（各章末）

---

## ■ 第4〜5章

### Sc-4-1 〜 Sc-5-2
**欠落が「痛み」になるシーンを必ず1か所含める**
（各シーン同形式）
**章末フック：**（各章末）

---

## ■ ミッドポイント（第5章最終）

### Sc-MP（ミッドポイント Scene）
**【行動】**：（主人公の目的が変化する瞬間）
**【感情】**：
**【思考】**：（転換の内的動機）
**【カメラ】**：（目的転換を視覚化するカメラワーク）
**【音響】**：
**フック：**（後半への強い引き）

---

## ■ 第6〜7章

### Sc-6-1 〜 Sc-7-2
**問いの答えが崩れ始める描写を必ず1か所含める**
（各シーン同形式）
**章末フック：**（各章末）

---

## ■ 転（第8章最終）

### Sc-T（転 Scene）
**【行動】**：（どんでん返しの瞬間）
**【感情】**：（衝撃・崩壊・書き換わり）
**【思考】**：（「あの時の〜は、実は〜だった」という認識の書き換え）
**【カメラ】**：（どんでん返しを最大化するカメラワーク）
**【音響】**：（沈黙・または音の変化）
**回収される伏線ID：**
**フック：**（どん底への落下予告）

---

## ■ 第9〜10章（結）

### Sc-9-1 〜 Sc-10-2
**クライマックスシーン（欠落との対峙）を最終章に配置**
（各シーン同形式）
**章末フック：**（最終章はなし）

---

## ■ エピローグ

### Sc-E（エピローグ Scene）
**【行動】**：
**【感情】**：（余韻・語らない余白）
**【思考】**：（なし or 最小限）
**【カメラ】**：（引きのカメラ・または主観）
**【音響】**：（余韻を生む音）
**余白：** あり（読後感を生む余白）
**最後の1文：**（S14で確定した案を転記）
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
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n[S23] シーン別プロット設計スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    print("  5レイヤー：行動/感情/思考/カメラワーク/音響")

    prev = load_prev_outputs(novel_type)

    # fix①: S22のS23引き渡しパラメータはファイル末尾にあるため、フルテキストから抽出
    from pathlib import Path as _Path
    _s22_path = _Path(__file__).parent.parent / "output" / "s22_scene_emotion" \
               / f"s22_emotion_latest_{novel_type}.md"
    if _s22_path.exists():
        _s22_full = _s22_path.read_text(encoding="utf-8")
        _idx = _s22_full.rfind("## ■ S23（シーン別プロット設計）への引き渡しパラメータ")
        prev["s22_table"] = _s22_full[_idx:] if _idx >= 0 else ""
    else:
        prev["s22_table"] = ""

    # fix②: S21の余白マップテーブルは中盤にあるため、余白マップ以降を抽出
    _s21_path = _Path(__file__).parent.parent / "output" / "s21_margin" \
               / f"s21_margin_latest_{novel_type}.md"
    if _s21_path.exists():
        _s21_full = _s21_path.read_text(encoding="utf-8")
        _idx21 = _s21_full.find("## ■ 余白マップ（全体）")
        prev["s21_map"] = _s21_full[_idx21:] if _idx21 >= 0 else ""
    else:
        prev["s21_map"] = ""

    world_setting    = config.get("world_setting", "")
    setting_confirmed = config.get("setting_confirmed", {})
    if world_setting:
        print(f"  世界観制約: {world_setting}")
    if setting_confirmed:
        print(f"  確定済み設定: {len(setting_confirmed)}件を注入")
    prompt = build_prompt(prev, novel_type, world_setting, setting_confirmed)
    print("  シーン別プロット設計中（Claude Sonnet）...")
    result = call_claude_sonnet(prompt)

    content = f"""# シーン別プロット設計
実行日時：{timestamp}
小説タイプ：{novel_type}

---

{result}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = OUTPUT_DIR / f"s23_{novel_type}_{timestamp}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Saved: {filepath.name}")

    latest_path = OUTPUT_DIR / f"s23_scene_latest_{novel_type}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] Latest: {latest_path.name}")

    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_シーン別プロット設計")},
            "スキル":     {"rich_text": txt("S23_シーン別プロット設計")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "未使用"}},
        }, "シーン別プロット設計", result)

    print("[S23] 完了\n")
    print("  ✅ 設計フェーズ（S1〜S23）完了")
    print("  次のステップ: S24（初版文章生成）")
    print(f"  コマンド例: python run_pipeline.py --skill 24 --type {novel_type}")

    return {"result": result, "timestamp": timestamp}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="short",
                        choices=["short", "medium", "long"])
    args = parser.parse_args()
    _config = load_config()
    _config["novel_type"] = args.type
    run(config=_config)
