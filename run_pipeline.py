# -*- coding: utf-8 -*-
"""
NOVEL_AUTOMATION パイプライン司令塔
Cursorから呼び出すメインスクリプト

使い方：
  python run_pipeline.py --skill 1        # Skills①のみ実行
  python run_pipeline.py --skill 1-4      # Skills①〜④を順番に実行
  python run_pipeline.py --skill 2        # Skills②のみ（前回の①結果を引き継ぎ）
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 共通ユーティリティ
sys.path.append(str(Path(__file__).parent))
from common.utils import load_config

def run_skill_1(config: dict) -> dict:
    """新S1：どんでん返し選択（旧S8）"""
    from skills.s01_plot_twist import run
    return run(config=config)


def run_skill_2_submission(config: dict) -> dict:
    """新S2：投稿形態設計"""
    from skills.s02_submission import run
    return run(config=config)

def run_skill_3(config: dict) -> dict:
    """新S3：主人公年齢設計"""
    from skills.s03_age_design import run
    return run(config=config)

def run_skill_4(config: dict) -> dict:
    """新S4：年齢差設計"""
    from skills.s04_age_gap import run
    return run(config=config)


# ============================================================
# 使用済み名前管理
# ============================================================

def _get_used_names_path() -> Path:
    return Path(__file__).parent / "output" / "used_names.json"

def _load_used_names() -> dict:
    p = _get_used_names_path()
    if p.exists():
        import json
        return json.loads(p.read_text(encoding="utf-8"))
    return {"names": [], "history": [], "last_updated": ""}

def _save_used_names(data: dict) -> None:
    import json
    from datetime import datetime
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    p = _get_used_names_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def register_names(names_str: str, story_title: str = "") -> None:
    """使用済み名前を登録する"""
    import json
    from datetime import datetime
    names = [n.strip() for n in names_str.split(",") if n.strip()]
    data  = _load_used_names()
    added = [n for n in names if n not in data["names"]]
    data["names"].extend(added)
    data["history"].append({
        "date":  datetime.now().strftime("%Y-%m-%d"),
        "names": added,
        "story": story_title,
    })
    _save_used_names(data)
    print(f"\n[名前登録] {len(added)}件追加: {', '.join(added)}")
    print(f"  累計登録数: {len(data['names'])}件")
    print(f"  全登録名: {', '.join(data['names'])}")

def show_used_names() -> None:
    """使用済み名前の一覧を表示"""
    data = _load_used_names()
    print(f"\n[使用済み名前一覧] 累計{len(data['names'])}件")
    print(f"  {', '.join(data['names']) if data['names'] else '（なし）'}")
    if data.get("history"):
        print("\n  登録履歴:")
        for h in data["history"][-5:]:  # 直近5件
            print(f"    {h['date']} [{h.get('story','無題')}] {', '.join(h['names'])}")



# ============================================================
# 登場人物数管理
# ============================================================

CHARACTER_COUNT_TABLE = {
    # (novel_type, series_mode) → (recommended, max)
    ("short",  False): (5, 6),
    ("medium", False): (6, 7),
    ("short",  True):  (5, 7),
    ("medium", True):  (6, 8),
    ("long",   True):  (8, 10),
}


def _resolve_character_count(config: dict) -> tuple:
    """登場人物数の推奨値と上限値を返す。手動指定がなければ種別から自動決定。"""
    manual = config.get("character_count", None)
    novel_type  = config.get("novel_type", "short")
    series_mode = config.get("series_mode", False)
    key = (novel_type, bool(series_mode))
    recommended, maximum = CHARACTER_COUNT_TABLE.get(key, (5, 6))
    if manual is not None:
        return int(manual), maximum
    return recommended, maximum


def _save_character_count_to_config(config: dict) -> None:
    """登場人物数をconfig.yamlに永続保存する。"""
    import yaml as _yaml
    recommended, maximum = _resolve_character_count(config)
    base = Path(__file__).parent / "config.yaml"
    raw  = _yaml.safe_load(base.read_text(encoding="utf-8")) or {}
    raw["character_count"]     = recommended
    raw["character_count_max"] = maximum
    base.write_text(
        _yaml.dump(raw, allow_unicode=True, default_flow_style=False),
        encoding="utf-8"
    )


def _save_tone_to_config(tone: str) -> None:
    """トーン設定をconfig.yamlに保存する（tone_ruleも自動生成）"""
    import yaml
    _tone_map = {
        "light_gag":    "明るめ＋ギャグ寄り（テンポが速い・笑いや軽さを随所に）",
        "light_normal": "明るめ＋普通（読みやすく・重すぎない・希望感のある文体）",
        "dark_normal":  "暗め＋普通（緊張感があるが読みやすい・重すぎない）",
        "dark_serious": "暗め＋シリアス（重厚・緊張感・感情の抑制・静かな深さ）",
    }
    tone_rule = f"【物語のトーン】{_tone_map.get(tone, '')}" if tone else ""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw["tone"] = tone
    raw["tone_rule"] = tone_rule
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False)

def _save_viewpoint_to_config(writing: dict) -> None:
    """視点設定をconfig.yamlに保存し、viewpoint_ruleを自動生成する"""
    import yaml

    # viewpoint_ruleを自動生成（S25〜S28が読み込む文字列）
    vp        = writing.get("viewpoint", "third_limited")
    protag    = writing.get("protagonist", "主人公")
    mono      = writing.get("monologue_style", "third")
    fp        = writing.get("first_person", "")

    if vp == "third_limited":
        pronoun_rule = f"「彼」「彼女」は使わず「{protag}」と書く"
        mono_rule    = "モノローグも三人称的独白で統一" if mono == "third" else "モノローグは一人称的独白で統一"
        rule = (f"三人称限定視点（{protag}視点）。{pronoun_rule}。"
                f"{mono_rule}。他キャラの内面は{protag}の観察経由のみ。")
    elif vp == "first":
        fp_str = fp or "私"
        rule = (f"一人称視点（{fp_str}）。地の文は「{fp_str}は〜」で統一。"
                f"他キャラの内面は推測・観察のみ。")
    elif vp == "third_omniscient":
        rule = "三人称全知視点。全キャラの内面描写可。代名詞（彼・彼女）使用可。"
    else:
        rule = ""

    writing["viewpoint_rule"] = rule

    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw["viewpoint_rule"] = rule
    raw.setdefault("writing", {}).update(writing)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False)


def run_skill_5_gender(config: dict) -> dict:
    """新S5：性別・炸点・熱量設計"""
    from skills.s05_gender_design import run
    return run(config=config)

def run_skill_6_gravity(config: dict) -> dict:
    """新S6：関係性重力設計"""
    from skills.s06_gravity import run
    return run(config=config)

def run_skill_5(config: dict) -> dict:
    from skills.s06_trauma import run
    return run(config=config)

def run_skill_6(config: dict, char_name: str = None, char_index: int = None) -> dict:
    from skills.s07_char_detail import run
    return run(config=config, char_name=char_name, char_index=char_index)

def run_skill_7_philosophy(config: dict) -> dict:
    """新S7：哲学的問い設計"""
    from skills.s07_philosophy import run
    return run(config=config)

def run_skill_7(config: dict) -> dict:
    from skills.s08_char_relation import run
    return run(config=config)

def run_skill_8_emotion(config: dict) -> dict:
    """新S8：感情設計"""
    from skills.s08_emotion import run
    return run(config=config)

def run_skill_10_character(config: dict) -> dict:
    """新S10：キャラクター設計（使用禁止名を自動注入）"""
    from skills.s10_character import run
    if not config.get("series_mode"):
        data = _load_used_names()
        if data["names"]:
            config["forbidden_names"] = data["names"]
            print(f"  [名前チェック] 使用禁止: {', '.join(data['names'])}")
    return run(config=config)

def run_skill_9_5_similarity(config: dict) -> dict:
    """S9_5：類似性チェック"""
    from skills.s9_5_similarity import run
    return run(config=config)

def run_skill_29_integrated(config: dict, section_index: int = None) -> dict:
    """新S29：統合出力（S26〜S28をまとめ）"""
    from skills.s29_integrated import run
    return run(config=config, section_index=section_index)

def run_skill_28_monologue(config: dict, section_index: int = None) -> dict:
    """新S28：モノローグ強化"""
    from skills.s28_monologue import run
    return run(config=config, section_index=section_index)

def run_skill_27_description(config: dict, section_index: int = None) -> dict:
    """新S27：情景描写強化"""
    from skills.s27_description import run
    return run(config=config, section_index=section_index)

def run_skill_26_dialogue(config: dict, section_index: int = None) -> dict:
    """新S26：セリフ強化（キャラ別）"""
    from skills.s26_dialogue import run
    return run(config=config, section_index=section_index)

def run_skill_25_rhythm(config: dict, section_index: int = None) -> dict:
    """新S25：リズム・文体調整"""
    from skills.s25_rhythm import run
    return run(config=config, section_index=section_index)

def run_skill_24_draft(config: dict, section_index: int = None) -> dict:
    """新S24：初版文章生成"""
    from skills.s24_draft import run
    return run(config=config, section_index=section_index)

def run_skill_23_scene_plot(config: dict) -> dict:
    """新S23：シーン別プロット設計"""
    from skills.s23_scene_plot import run
    return run(config=config)

def run_skill_22_scene_emotion(config: dict) -> dict:
    """新S22：シーン別感情設計"""
    from skills.s22_scene_emotion import run
    return run(config=config)

def run_skill_21_margin(config: dict) -> dict:
    """新S21：余白設計"""
    from skills.s21_margin import run
    return run(config=config)

def run_skill_20_chapter(config: dict) -> dict:
    """新S20：章プロット設計（long専用）"""
    from skills.s20_chapter_plot import run
    return run(config=config)

def run_skill_19_act(config: dict) -> dict:
    """新S19：起承転結設計"""
    from skills.s19_act_structure import run
    return run(config=config)

def run_skill_18_foreshadow(config: dict) -> dict:
    """新S18：伏線設計"""
    from skills.s18_foreshadow import run
    return run(config=config)

def run_skill_17_resonance(config: dict) -> dict:
    """新S17：共鳴点設計"""
    from skills.s17_resonance import run
    return run(config=config)

def run_skill_16_distance(config: dict) -> dict:
    """新S16：距離感設計"""
    from skills.s16_distance import run
    return run(config=config)

def run_skill_15_subplot(config: dict) -> dict:
    """新S15：並行線設計"""
    from skills.s15_subplot import run
    return run(config=config)

def run_skill_14_plot(config: dict) -> dict:
    """新S14：全体プロット設計"""
    from skills.s14_plot_main import run
    return run(config=config)

def run_skill_13_deficiency(config: dict) -> dict:
    """新S13：キャラ欠落分析"""
    from skills.s13_deficiency import run
    return run(config=config)

def run_skill_12_trauma(config: dict) -> dict:
    """新S12：トラウマ設計"""
    from skills.s12_trauma import run
    return run(config=config)

def run_skill_11_personality(config: dict) -> dict:
    """新S11：X軸Y軸性格設計"""
    from skills.s11_personality import run
    return run(config=config)

def run_skill_8(config: dict) -> dict:
    from skills.s01_plot_twist import run
    return run(config=config)

def run_skill_9_theme(config: dict) -> dict:
    """新S9：テーマ設計"""
    from skills.s09_theme import run
    return run(config=config)

def run_skill_9(config: dict) -> dict:
    from skills.s09_parallel_line import run
    return run(config=config)

def run_skill_10(config: dict) -> dict:
    from skills.s10_plot_main import run
    return run(config=config)

def run_skill_11(config: dict) -> dict:
    from skills.s11_chapter_plot import run
    return run(config=config)

def run_skill_12(config: dict) -> dict:
    from skills.s12_scene_plot import run
    return run(config=config)

def run_skill_13(config: dict, section_index: int = None) -> dict:
    from skills.s13_draft_writing import run
    return run(config=config, section_index=section_index)

def run_skill_14(config: dict, section_key: str = None) -> dict:
    from skills.s14_dialogue import run
    return run(config=config, section_key=section_key)

def run_skill_15(config: dict, section_key: str = None) -> dict:
    from skills.s15_description import run
    return run(config=config, section_key=section_key)

def run_skill_16(config: dict, section_key: str = None) -> dict:
    from skills.s16_revision import run
    return run(config=config, section_key=section_key)

def run_skill_2_4(plot: str, config: dict) -> dict:
    from skills.s03_s05_character import (
        run_char_count, run_char_x_axis, run_char_y_axis, save_all
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    r2 = run_char_count(plot, config)
    r3 = run_char_x_axis(r2["char_list"], config)
    r4 = run_char_y_axis(r2["char_list"], r3["x_axis"], config)
    save_all(r2["char_list"], r3["x_axis"], r4["y_axis"], config, timestamp)
    return {**r2, **r3, **r4}

def load_latest_plot(base_dir: Path, novel_type: str = None) -> str:
    """最新のs01出力ファイルからプロットを読み込む
    novel_typeを指定すると該当タイプの最新ファイルを使用
    """
    output_dir = base_dir / "output" / "s02_idea_decision"
    if not output_dir.exists():
        return ""

    # novel_typeが指定された場合はそのタイプのファイルのみ対象
    if novel_type:
        files = sorted(output_dir.glob(f"s02_{novel_type}_*.md"), reverse=True)
        if not files:
            print(f"  [WARNING] {novel_type}タイプの①結果が見つかりません。全ファイルから最新を使用します。")
            files = sorted(output_dir.glob("s02_*.md"), reverse=True)
    else:
        files = sorted(output_dir.glob("s02_*.md"), reverse=True)

    if not files:
        return ""

    # ファイル一覧を表示して選択させる
    print("\n  利用可能な①結果ファイル：")
    for i, f in enumerate(files[:10], 1):
        print(f"  {i}. {f.name}")

    if len(files) == 1:
        latest = files[0]
        print(f"  → 自動選択: {latest.name}")
    else:
        try:
            choice = input("  使用するファイル番号を入力（Enterで最新を使用）: ").strip()
            if choice == "" or not choice.isdigit():
                latest = files[0]
            else:
                idx = int(choice) - 1
                latest = files[min(idx, len(files)-1)]
        except Exception:
            latest = files[0]
        print(f"  → 選択: {latest.name}")

    with open(latest, "r", encoding="utf-8") as f:
        file_content = f.read()
    # プロット・あらすじ・コメディ要素を含む全体を返す
    # プロローグセクション以降のメタ情報を除いたメインコンテンツを抽出
    if "---" in file_content:
        # ヘッダー行を除いたコンテンツ部分を返す
        main_content = file_content.split("---", 1)[-1].strip()
        return main_content[:4000]
    return file_content[:4000]

def main():
    parser = argparse.ArgumentParser(description="Novel Automation Pipeline")
    parser.add_argument("--skill", type=str, default="1",
                        help="実行するスキル番号（例：1, 2, 1-4）")
    parser.add_argument("--use-existing", action="store_true",
                        help="Skills①を実行せず既存の①結果を使って②以降を実行")
    parser.add_argument("--type", type=str, default=None,
                        choices=["short", "medium", "long"],
                        help="小説タイプ（short=5万字/medium=10万字/long=20万字）")
    parser.add_argument("--section", type=int, default=None,
                        help="Skills⑬用：生成するセクション番号（0始まり）。省略すると全セクション順番に生成")
    parser.add_argument("--section-name", type=str, default=None,
                        help="Skills⑭用：対象セクション名（例：prologue, ch1）")
    parser.add_argument("--char-name", type=str, default=None,
                        help="Skills⑥用：特定キャラクター名（例：傘田アキ）")
    parser.add_argument("--age-range", type=str, default="free",
                        choices=["high-school", "college", "twenties", "thirties", "free", "young-adult", "mix"],
                        help=(
                            "S3-5用：キャラクター年齢レンジ\n"
                            "high-school: 主人公15-17歳（高校生）\n"
                            "college    : 主人公18-22歳（大学生・社会人初期）\n"
                            "young-adult: 主人公20-25歳（若手社会人）\n"
                            "mix        : 主人公15-22歳（LN標準・デフォルト）"
                        ))
    parser.add_argument("--theme", type=str, default=None,
                        help=(
                            "S02用：指定テーマ（例：--theme 1-1）\n"
                            "1-1:修行・鍛錬 / 1-2:立身出世 / 1-3:精神成長 / 1-4:復活再起 / 1-5:才能開花\n"
                            "2-1:バトル / 2-2:サバイバル / 2-3:スパイ潜入 / 2-4:犯罪 / 2-5:復讐\n"
                            "3-1:ハイファンタジー / 3-2:ローファンタジー / 3-3:ミステリー / 3-4:サスペンス / 3-5:ホラー\n"
                            "4-1:冒険旅行 / 4-2:逃避行 / 4-3:探索 / 4-4:配達任務 / 4-5:帰郷\n"
                            "5-1:天災 / 5-2:パンデミック / 5-3:戦争 / 5-4:技術暴走\n"
                            "6-1:お仕事系 / 6-2:恋愛系"
                        ))
    parser.add_argument("--hero-type", type=str, default="same-age",
                        choices=["same-age","older-sister","younger","cool-senior","rival","age-gap","mutual"],
                        help="S2/S3-5用：ヒロインタイプ")
    parser.add_argument("--pairing", type=str, default="male-female",
                        choices=["male-female","female-male","male-buddy","female-buddy",
                                 "male-neutral","female-neutral"],
                        help="S2/S3-5用：主人公×ヒロインの性別構造\n"
                             "male-neutral  : 男主人公×性別不明/中性の相方（怪物・異種族など）\n"
                             "female-neutral: 女主人公×性別不明/中性の相方（怪物・異種族など）")
    parser.add_argument("--contest", type=str, default=None,
                        choices=["note", "kakuyomu", "kakugawa_chara", "everystory"],
                        help="投稿コンテスト向け制約を注入")
    parser.add_argument("--value-reversal", type=str, default=None,
                        choices=["V1", "V2", "V3", "V4", "V5", "V6", "V7"],
                        help="S1用：価値観反転タイプを指定（省略時はランダム）")
    parser.add_argument("--twist", type=str, default=None,
                        choices=["ドラドラ", "ドラウル", "ドラフラ", "ウルドラ", "フラドラ",
                                 "ウルフラ", "フラウル", "レッドラ", "ハナサカ", "アオトリ"],
                        help="S1用：どんでん返しパターンを手動指定（省略時はV×重みで自動抽選）")
    parser.add_argument("--weight-emotion",    type=int, default=None, help="S2手動モード：感情刺激度 0-100")
    parser.add_argument("--weight-character",  type=int, default=None, help="S2手動モード：キャラ魅力度 0-100")
    parser.add_argument("--weight-tempo",      type=int, default=None, help="S2手動モード：テンポ 0-100")
    parser.add_argument("--weight-visual",     type=int, default=None, help="S2手動モード：視覚性 0-100")
    parser.add_argument("--weight-literary",   type=int, default=None, help="S2手動モード：文学性 0-100")
    parser.add_argument("--weight-commercial", type=int, default=None, help="S2手動モード：市場性 0-100")
    parser.add_argument("--writing-ai", type=str, default="claude",
                        choices=["claude", "openai"],
                        help="S24用：初版文章生成AI（claude=Claude Sonnet / openai=OpenAI o1/o3）")
    parser.add_argument("--openai-model", type=str, default="gpt-5.5-2026-04-23",
                        choices=["gpt-5.5-2026-04-23", "o3-pro", "o3", "o4-mini", "gpt-4o"],
                        help="S24用：OpenAI使用時のモデル指定（省略時: gpt-5.5-2026-04-23）")
    parser.add_argument("--reasoning-effort", type=str, default="high",
                        choices=["none", "low", "medium", "high", "xhigh"],
                        help="S24用：GPT-5.5のモード（none/low=Instant / high/xhigh=Thinking）")
    parser.add_argument("--char-count", type=int, default=4,
                        help="S10用：設計する登場人物数（省略時: 4）")
    parser.add_argument("--extra-char-role", type=str, default="",
                        help="S10用：5人目以降の追加キャラの役割（例: 相方の友人）")
    parser.add_argument("--emotion-ending", type=str, default="",
                        help="S8用：読後感を手動指定（loss/catharsis/hope等）")
    parser.add_argument("--viewpoint", type=str, default=None,
                        choices=["third_limited", "first", "third_omniscient"],
                        help="S5〜S28用：視点タイプ（third_limited/first/third_omniscient）")
    parser.add_argument("--tone", type=str, default=None,
                        choices=["light_gag", "light_normal", "dark_normal", "dark_serious"],
                        help="物語のトーン（light_gag/light_normal/dark_normal/dark_serious）")
    parser.add_argument("--character-count", type=int, default=None,
                        help="S2用：登場人物数（省略時は種別から自動設定）\n"
                             "short単発→推奨5/上限6 / medium単発→推奨6/上限7\n"
                             "shortシリーズ→推奨5/上限7 / mediumシリーズ→推奨6/上限8\n"
                             "longシリーズ→推奨8/上限10")
    parser.add_argument("--register-names", type=str, default=None,
                        help="使用済み名前を登録（カンマ区切り例：湊,礼,冬子）")
    parser.add_argument("--show-names", action="store_true",
                        help="使用済み名前の一覧を表示")
    parser.add_argument("--series", action="store_true",
                        help="連作小説モード（名前チェック・登録をスキップ）")
    parser.add_argument("--protagonist", type=str, default=None,
                        help="視点キャラの呼称（例：湊, 智晶, 私）")
    parser.add_argument("--first-person", type=str, default=None,
                        help="一人称語（first視点のみ。例：私, 俺, 僕）")
    parser.add_argument("--monologue-style", type=str, default=None,
                        choices=["third", "first"],
                        help="モノローグスタイル（third=三人称的独白 / first=一人称的独白）")
    parser.add_argument("--gravity-main", type=str, default="auto",
                        help="S6用：主軸重力項目（auto/protection/dependence等）")
    parser.add_argument("--gravity-sub",  type=str, default="auto",
                        help="S6用：副軸重力項目（auto/protection/dependence等）")
    parser.add_argument("--char-index", type=int, default=None,
                        help="Skills⑥用：キャラクター番号（1始まり・実行時に一覧表示）")
    parser.add_argument("--auto-check", action="store_true",
                        help="各スキル実行後に自動整合性チェックを行う")
    parser.add_argument("--target", type=int, default=50000,
                        help="S31用：目標文字数・上限（超過NG）（省略時: 50000）")
    args = parser.parse_args()

    config = load_config()
    skill_arg = args.skill
    use_existing = args.use_existing

    # --typeが指定された場合はconfigを上書き
    # 名前管理コマンド（スキル実行前に処理して終了）
    if getattr(args, "show_names", False):
        show_used_names()
        return
    if getattr(args, "register_names", None):
        story = config.get("novel_title", "")
        register_names(args.register_names, story_title=story)
        return

    config["novel_type"] = args.type
    if args.tone:
        config["novel_tone"] = args.tone

    # 視点設定（コマンドライン指定がconfig.yamlを上書き）
    writing = config.setdefault("writing", {})
    if args.viewpoint:
        writing["viewpoint"]       = args.viewpoint
    if args.protagonist:
        writing["protagonist"]     = args.protagonist
    if getattr(args, "first_person", None):
        writing["first_person"]    = args.first_person
    if getattr(args, "monologue_style", None):
        writing["monologue_style"] = args.monologue_style
    writing.setdefault("viewpoint",       "third_limited")
    writing.setdefault("protagonist",     "主人公")
    writing.setdefault("first_person",    "")
    writing.setdefault("monologue_style", "third")
    if args.age_range:
        config["age_range"] = args.age_range
    if args.hero_type:
        config["hero_type"] = args.hero_type
    if args.pairing:
        config["pairing"] = args.pairing
    if args.contest:
        config["contest"] = args.contest
        print(f"  コンテスト向け：{args.contest}")
    if args.theme:
        config["novel_theme"] = args.theme
        type_labels = {"short": "短編（5万字）", "medium": "中編（10万字）", "long": "長編（20万字）"}
        if args.type:
            print(f"小説タイプ：{type_labels[args.type]}")
    if args.value_reversal:
        config["value_reversal"] = args.value_reversal
    if args.twist:
        config["twist_pattern"] = args.twist
    if getattr(args, "series", False):
        config["series_mode"] = True  # S01以降で参照可能
    if args.char_count:
        config["char_count"]      = args.char_count  # 旧キー（後方互換）
        config["character_count"] = args.char_count  # 新キー（S02管理分と統一）
    if args.extra_char_role:
        config["extra_char_role"] = args.extra_char_role
    if args.writing_ai:
        config["writing_ai"] = args.writing_ai
    if args.openai_model:
        config["openai_model"] = args.openai_model
    if args.reasoning_effort:
        config["reasoning_effort"] = args.reasoning_effort
    if args.emotion_ending:
        config["emotion_ending"] = args.emotion_ending
    if args.gravity_main:
        config["gravity_main"] = args.gravity_main
    if args.gravity_sub:
        config["gravity_sub"] = args.gravity_sub
    if args.target:
        config["target"] = args.target
    for key, attr in [
        ("weight_emotion",    args.weight_emotion),
        ("weight_character",  args.weight_character),
        ("weight_tempo",      args.weight_tempo),
        ("weight_visual",     args.weight_visual),
        ("weight_literary",   args.weight_literary),
        ("weight_commercial", args.weight_commercial),
    ]:
        if attr is not None:
            config[key] = attr

    print("=" * 60)
    print(f"NOVEL_AUTOMATION パイプライン")
    print(f"実行スキル：{skill_arg}")
    if use_existing:
        print(f"モード：既存の①結果を使用")
    print("=" * 60)

    context = {}

    # --use-existingの場合は①をスキップして既存ファイルからプロット読み込み
    if use_existing:
        base_dir = Path(__file__).parent
        plot = load_latest_plot(base_dir, config.get("novel_type"))
        if not plot:
            print("[ERROR] 既存の①結果が見つかりません。先に --skill 2 を実行してください。")
            sys.exit(1)
        context["plot"] = plot
        print(f"  プロット読み込み完了（{len(plot)}文字）\n")

    # スキル番号を解析
    if "-" in skill_arg:
        start, end = map(int, skill_arg.split("-"))
        skill_range = range(start, end + 1)
    else:
        skill_range = [int(skill_arg)]

    # ②③④はまとめて1回だけ実行
    run_2_4 = any(n in skill_range for n in [2, 3, 4])
    executed_2_4 = False

    for skill_num in skill_range:
        if skill_num == 1:
            # 新S1：どんでん返し選択（旧S8）
            result = run_skill_1(config)
            context.update(result)

        elif skill_num == 2:
            # 新S2：投稿形態設計 ＋ トーン設定の保存
            if use_existing:
                print("[INFO] --use-existing モードのためSkills②をスキップします")
                continue
            if getattr(args, "tone", None):
                config["tone"] = args.tone
                _save_tone_to_config(args.tone)
                _tone_labels = {
                    "light_gag":    "明るめ＋ギャグ寄り",
                    "light_normal": "明るめ＋普通",
                    "dark_normal":  "暗め＋普通",
                    "dark_serious": "暗め＋シリアス",
                }
                print(f"\n[S2] トーン設定をconfig.yamlに保存しました")
                print(f"  tone: {args.tone}（{_tone_labels.get(args.tone, '')}）")
            # 登場人物数をconfigとconfig.yamlに保存
            if getattr(args, "character_count", None):
                config["character_count"] = args.character_count
            rec, mx = _resolve_character_count(config)
            config["character_count"]     = rec
            config["character_count_max"] = mx
            _save_character_count_to_config(config)
            print(f"[S2] 登場人物数をconfig.yamlに保存しました")
            print(f"  推奨: {rec}名 / 上限: {mx}名")
            result = run_skill_2_submission(config)
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(2, config.get("novel_type", "short"), config)
                if not prompt_continue(2, check):
                    break

        elif skill_num == 3:
            # 新S3：主人公年齢設計
            result = run_skill_3(config)
            context.update(result)

        elif skill_num == 4:
            # 新S4：年齢差設計
            result = run_skill_4(config)
            context.update(result)

        elif skill_num == 5:
            # 新S5：性別・炸点・熱量設計 ＋ 視点設定の保存
            result = run_skill_5_gender(config)
            context.update(result)

            # --viewpoint等が指定されていればconfig.yamlに永続保存
            writing = config.get("writing", {})
            if any([args.viewpoint, args.protagonist,
                    getattr(args, "first_person", None),
                    getattr(args, "monologue_style", None)]):
                _save_viewpoint_to_config(writing)
                print(f"\n[S5] 視点設定をconfig.yamlに保存しました")
                print(f"  viewpoint       : {writing.get('viewpoint')}")
                print(f"  protagonist     : {writing.get('protagonist')}")
                print(f"  monologue_style : {writing.get('monologue_style')}")

        elif skill_num == 6:
            # 新S6：関係性重力設計
            result = run_skill_6_gravity(config)
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(6, config.get("novel_type", "short"), config)
                if not prompt_continue(6, check):
                    break
        elif skill_num == 7:
            # 新S7：哲学的問い設計
            result = run_skill_7_philosophy(config)
            context.update(result)

        elif skill_num == 70:  # 旧キャラクター詳細設計（旧6）
            result = run_skill_6(config,
                                  char_name=getattr(args, 'char_name', None),
                                  char_index=getattr(args, 'char_index', None))
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(7, config.get("novel_type", "short"), config)
                if not prompt_continue(7, check):
                    break
        elif skill_num == 8:
            # 新S8：感情設計
            result = run_skill_8_emotion(config)
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(8, config.get("novel_type", "short"), config)
                if not prompt_continue(8, check):
                    break
        elif skill_num == 8:
            result = run_skill_8(config)
            context.update(result)

        elif skill_num == 9:
            # 新S9：テーマ設計 ＋ 視点設定の保存
            result = run_skill_9_theme(config)
            context.update(result)

            # --viewpoint等が指定されていればconfig.yamlに永続保存
            writing = config.get("writing", {})
            if any([getattr(args, "viewpoint", None),
                    getattr(args, "protagonist", None),
                    getattr(args, "first_person", None),
                    getattr(args, "monologue_style", None)]):
                _save_viewpoint_to_config(writing)
                print(f"\n[S9] 視点設定をconfig.yamlに保存しました")
                print(f"  viewpoint       : {writing.get('viewpoint', '未設定')}")
                print(f"  protagonist     : {writing.get('protagonist', '未設定')}")
                print(f"  monologue_style : {writing.get('monologue_style', '未設定')}")
                print(f"  viewpoint_rule  : {writing.get('viewpoint_rule', '（自動生成）')[:50]}")
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(9, config.get("novel_type", "short"), config)
                if not prompt_continue(9, check):
                    break
        elif skill_num == 95:
            # S9_5：類似性チェック（S9完了後・S10開始前）
            result = run_skill_9_5_similarity(config)
            context.update(result)

        elif skill_num == 10:
            # 新S10：キャラクター設計
            if getattr(args, "series", False):
                config["series_mode"] = True
            result = run_skill_10_character(config)
            context.update(result)
            if not getattr(args, "series", False):
                print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"  [名前登録] S10で決定した名前を確認後、以下で登録してください：")
                print('  python run_pipeline.py --register-names "名前1,名前2,..."')
                print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(10, config.get("novel_type", "short"), config)
                if not prompt_continue(10, check):
                    break
        elif skill_num == 11:
            # 新S11：X軸Y軸性格設計
            result = run_skill_11_personality(config)
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(11, config.get("novel_type", "short"), config)
                if not prompt_continue(11, check):
                    break
        elif skill_num == 12:
            # 新S12：トラウマ設計
            result = run_skill_12_trauma(config)
            context.update(result)
            if getattr(args, 'auto_check', False):
                from auto_check import run_check, prompt_continue
                check = run_check(12, config.get("novel_type", "short"), config)
                if not prompt_continue(12, check):
                    break
        elif skill_num == 13:
            # 新S13：キャラ欠落分析
            result = run_skill_13_deficiency(config)
            context.update(result)
            context.update(result)

        elif skill_num == 14:
            # 新S14：全体プロット設計
            result = run_skill_14_plot(config)
            context.update(result)
            context.update(result)

        elif skill_num == 15:
            # 新S15：並行線設計
            result = run_skill_15_subplot(config)
            context.update(result)
            context.update(result)

        elif skill_num == 16:
            # 新S16：距離感設計
            result = run_skill_16_distance(config)
            context.update(result)
            context.update(result)

        elif skill_num == 17:
            # 新S17：共鳴点設計
            result = run_skill_17_resonance(config)
            context.update(result)

        elif skill_num == 18:
            # 新S18：伏線設計
            result = run_skill_18_foreshadow(config)
            context.update(result)

        elif skill_num == 19:
            # 新S19：起承転結設計
            result = run_skill_19_act(config)
            context.update(result)

        elif skill_num == 20:
            # 新S20：章プロット設計（long専用・short/mediumは自動スキップ）
            result = run_skill_20_chapter(config)
            context.update(result)

        elif skill_num == 21:
            # 新S21：余白設計
            result = run_skill_21_margin(config)
            context.update(result)

        elif skill_num == 22:
            # 新S22：シーン別感情設計
            result = run_skill_22_scene_emotion(config)
            context.update(result)

        elif skill_num == 23:
            # 新S23：シーン別プロット設計
            result = run_skill_23_scene_plot(config)
            context.update(result)

        elif skill_num == 24:
            # 新S24：初版文章生成
            sec_idx = getattr(args, 'section', None)
            result = run_skill_24_draft(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 25:
            # 新S25：リズム・文体調整
            sec_idx = getattr(args, 'section', None)
            result = run_skill_25_rhythm(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 26:
            # 新S26：セリフ強化（キャラ別）
            sec_idx = getattr(args, 'section', None)
            result = run_skill_26_dialogue(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 27:
            # 新S27：情景描写強化
            sec_idx = getattr(args, 'section', None)
            result = run_skill_27_description(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 28:
            # 新S28：モノローグ強化
            sec_idx = getattr(args, 'section', None)
            result = run_skill_28_monologue(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 29:
            # 新S29：統合出力（S26〜S28まとめ）
            sec_idx = getattr(args, 'section', None)
            result = run_skill_29_integrated(config, section_index=sec_idx)
            context.update(result)

        elif skill_num == 30:
            # S30：セリフ再強化
            sys.path.insert(0, str(Path(__file__).parent / "skills"))
            from s30_dialogue_enhance import run as _run_s30
            sec_idx = getattr(args, 'section', None)
            result = _run_s30(config=config, section_index=sec_idx)
            context.update(result or {})

        elif skill_num == 31:
            # S31：既視感除去＋文章量調整
            # PASS1: Gemini Pro（全セクション横断・繰り返しパターン検出）
            # PASS2: Claude Sonnet（セクション別圧縮）
            # PASS3: 差分レポート集約
            sys.path.insert(0, str(Path(__file__).parent / "skills"))
            from s31_trim import run as _run_s31
            result = _run_s31(config=config)
            context.update(result or {})

        elif skill_num == 32:
            # S32：整合性チェック準備（ファイル生成のみ・Opus手動実行）
            # 出力: s32_input（添付用統合テキスト）+ s32_prompt（コピペ用プロンプト）
            sys.path.insert(0, str(Path(__file__).parent / "skills"))
            from s32_check import run as _run_s32
            result = _run_s32(config=config)
            context.update(result or {})

        else:
            print(f"[INFO] Skills⑱以降は順次実装予定です（skill_num={skill_num}）")

    print("\n" + "=" * 60)
    print("パイプライン完了")
    print("=" * 60)

if __name__ == "__main__":
    main()
