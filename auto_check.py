# -*- coding: utf-8 -*-
"""
auto_check.py：各ステップ後の自動整合性チェック
run_pipeline.py から --auto-check フラグで呼び出される
"""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from common.utils import load_config, call_claude_sonnet

BASE_DIR = Path(__file__).parent

# スキルごとのチェック定義
CHECK_DEFINITIONS = {
    2: {
        "name": "アイデア決定チェック",
        "output_dir": "s02_idea_decision",
        "pattern": "s02_*.md",
        "criteria": """
【S2アイデア決定の整合性チェック基準】

【重要：チェック対象の範囲】
S1の「キャラクター名・年齢・性別・職業」はS2で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
チェックするのは「どんでん返しパターンの構造」のみ。

【コンテストモード（--contestが指定された場合）】
S2の出力に以下のコンテスト要件が含まれている場合は✅合格とする。
どんでん返しパターンとの不一致は問題なし（コンテスト要件が優先）。

■ note創作大賞モードの合格条件
・一文コンセプトが記載されている
・冒頭3行（感情・事件・違和感から始まる）が設計されている
・各章の文字数が1500〜2500文字で指定されている
・恋愛要素または感情的な関係性が含まれている
・現代舞台である

→ 上記5点が確認できれば、どんでん返しパターンの不一致があっても✅合格とする。

① どんでん返しパターンの構造反映（最重要）
・S1で選んだパターン番号（1〜10）の「構造」がプロットに反映されているか
・例：アオトリ（10）→「目的・答えが実は主人公の内側・そばにあった」構造
・例：ハナサカ（9）→「死んだと思っていた目的が実は生きていた」構造
・例：ドラドラ（1）→「外部の敵Aだと思ったら別の外部の敵Bだった」構造
・キャラクター名・設定の変更は問題なし（✅として扱う）

② テーマ・トーンの整合
・指定テーマ（--themeのA・B）の要素が物語に含まれているか
・指定トーン（balance/pop/serious）に沿った雰囲気か

③ プロット基本構造
・主人公の欲望・欠落・変化が明示されているか
・テーマが一文で表現されているか

【判定基準】
✅ 合格：①のパターン構造が反映されている（キャラ変更は無視）
⚠️ 要確認：①が弱い、②③に問題
❌ 問題あり：①のパターン構造が全く反映されていない
""",
    },
    "3-5": {
        "name": "キャラクター設計チェック",
        "output_dir": "s03_s05_character",
        "pattern": "s03_s05_character_*.md",
        "criteria": """
【S3-5キャラクター設計の整合性チェック基準】
【S1との整合性について（重要）】
S1（どんでん返し設計）のキャラクター名・年齢・性別・職業はS2以降で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
確認するのは「どんでん返しパターンの構造」のみ。キャラ名の違いは❌にしない。



① 必須キャラクターの存在（最重要）
・主人公・ヒロイン/相棒・本敵・偽敵が揃っているか
・揃っていれば①は合格

② X軸・Y軸性格バランス（記載なしは問題なし）
・X軸・Y軸の記載がなくても❌にしない（後のS7詳細設計で設定するため）
・記載がある場合のみバランスを確認する
・ジェスター不在も問題なし（S7詳細設計で補完可能なため）

③ どんでん返しとの整合（重要）
・偽敵と本敵の設定がS1のどんでん返しパターンと矛盾していないか

④ プロットとの整合（重要）
・主要キャラクターの役職・役割がS2のプロットと一致しているか
・細部の不一致は⚠️とし、❌にしない

【判定基準】
✅ 合格：①③④が問題なし（②は任意）
⚠️ 要確認：③④に軽微な不整合
❌ 問題あり：①で必須キャラが欠けている、③でどんでん返しと完全に矛盾
""",
    },
    6: {
        "name": "トラウマ設計チェック",
        "output_dir": "s06_trauma",
        "pattern": "s08_*.md",
        "criteria": """
【S6トラウマ設計の整合性チェック基準】
【S1との整合性について（重要）】
S1（どんでん返し設計）のキャラクター名・年齢・性別・職業はS2以降で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
確認するのは「どんでん返しパターンの構造」のみ。キャラ名の違いは❌にしない。



【短編の必須ルール】
以下の4名のトラウマが設計されていれば✅合格：
・主人公
・ヒロイン（または相棒①）
・偽敵
・本敵
それ以外のキャラのトラウマが未記載でも❌にしない（任意）。

① 必須4名のトラウマ存在確認
・上記4名のトラウマが設計されているか（短編の合格条件）

② 行動原理との接続（必須4名のみ確認）
・各キャラのトラウマが行動動機と論理的につながっているか

③ どんでん返しへの影響
・本敵のトラウマが「なぜ敵になったか」を説明できているか

④ 内的問題×欠落の組み合わせ
・同一作品内で同じ組み合わせのキャラが複数いないか

【判定基準】
✅ 合格：必須4名のトラウマが揃っている
⚠️ 要確認：必須4名の一部が未記載 or 行動原理との接続が弱い
❌ 問題あり：必須4名の2名以上が完全に未設計
""",
    },
    7: {
        "name": "キャラクター詳細設計チェック",
        "output_dir": "s07_char_detail",
        "pattern": "s08_*.md",
        "criteria": """
【S7キャラクター詳細設計の整合性チェック基準】
【S1との整合性について（重要）】
S1（どんでん返し設計）のキャラクター名・年齢・性別・職業はS2以降で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
確認するのは「どんでん返しパターンの構造」のみ。キャラ名の違いは❌にしない。



① 設計の完成度
・11カテゴリ（管理識別〜メタ総合）が主要キャラ分揃っているか
・文字切れ・途中終了がないか

② 基本情報の整合
・性別・年齢・職業がS3-5の設計と一致しているか
・一人称・口調がS3-5の性格設定（Y軸）と一致しているか

③ 能力・過去の整合
・特殊能力・武器がプロットで使われる内容と矛盾しないか
・過去・トラウマがS6のトラウマ設計と一致しているか

④ キャラクターアーク
・初期状態→最終到達点が変化として成立しているか
""",
    },
    8: {
        "name": "関係性設計チェック",
        "output_dir": "s08_char_relation",
        "pattern": "s08_*.md",
        "criteria": """
【S8関係性設計の整合性チェック基準】
【S1との整合性について（重要）】
S1（どんでん返し設計）のキャラクター名・年齢・性別・職業はS2以降で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
確認するのは「どんでん返しパターンの構造」のみ。キャラ名の違いは❌にしない。



① 全キャラ網羅
・全登場人物の関係が相関図に含まれているか

② 非対称性
・感情の一方通行・利用関係・秘密の非対称が3つ以上設計されているか

③ どんでん返しとの接続
・本敵が偽敵に見える関係性設計になっているか
・隠された関係性がどんでん返しに直結しているか

④ 変化の設計
・主要キャラの関係が序盤→中盤→終盤で変化するよう設計されているか
""",
    },
    9: {
        "name": "並行線設計チェック",
        "output_dir": "s09_parallel_line",
        "pattern": "s09_*.md",
        "criteria": """
【S9並行線設計の整合性チェック基準】

【重要：S9の出力形式について】
S9は各キャラの詳細設計をNotionに個別保存しており、ローカルファイルには概要のみ含まれる。
「並行線設定一覧」の表が存在すれば✅合格とする。
個別キャラの詳細が見えなくても❌にしない。
【S1との整合性について（重要）】
S1（どんでん返し設計）のキャラクター名・年齢・性別・職業はS2以降で変更されて構わない。
S2では年齢レンジ・テーマ・トーンの制約に合わせてキャラを再設計するため。
確認するのは「どんでん返しパターンの構造」のみ。キャラ名の違いは❌にしない。



① 全キャラ網羅（主人公以外）
・主人公以外の全登場人物の並行線パターンが設計されているか

② パターンの適切さ
・偽敵・本敵に「外部参入型」または「降下型」が使われているか
・主人公に近い人物に「早期収束型」が使われているか

③ 絡み合い設計
・物語のドラマが最大化する絡み合いポイントが3つ以上あるか

④ プロットとの整合
・各キャラの並行線の合流点がS2プロットの重要シーンと一致しているか
""",
    },
    10: {
        "name": "四幕構成プロットチェック",
        "output_dir": "s10_plot_main",
        "pattern": "s10_*_summary_*.md",
        "criteria": """
【S10四幕構成プロットチェック基準】

① 8プロットの完成
・プロローグ・起・非日常・承前半・ミッド・承後半・転・結が揃っているか

② 技法の適用
・B技法（記号化伏線）がプロローグ・起・承前半・ミッドに仕込まれているか
・F技法（サスペンス）が非日常・転・結に機能しているか
・E技法（書き出し設計）がプロローグに適用されているか

③ どんでん返しの準備
・転プロットでどんでん返しが発生する設計になっているか
・承後半で伏線回収が始まっているか

④ キャラクターの一貫性
・全キャラがS7詳細設計の性格・能力設定通りに動いているか
""",
    },
    11: {
        "name": "章構成プロットチェック",
        "output_dir": "s11_chapter_plot",
        "pattern": "s11_*.md",
        "criteria": """
【S11章構成プロットチェック基準】（長編専用）

① 章数・構成
・10章＋プロローグ＋エピローグが揃っているか

② 四幕との整合
・S10の8プロット（転・結・ミッドポイント等）が適切な章に配置されているか

③ テンポ
・各章の文字数目安が均等か（1章あたり12,000〜18,000字）

④ 伏線の流れ
・プロローグで仕込んだ伏線が適切な章で変奏・回収されているか
""",
    },
    12: {
        "name": "シーン構成チェック",
        "output_dir": "s12_scene_plot",
        "pattern": "s12_*_complete_*.md",
        "criteria": """
【S12シーン構成チェック基準】

① 全セクション網羅
・プロローグ〜エピローグの全セクションのシーン設計が揃っているか

② 感情3層設計
・主要シーンにLayer1（表向き）・Layer2（真意）・Layer3（身体反応）が設計されているか

③ 対立設計
・各シーンに対立軸が1つ以上明示されているか

④ 伏線ID管理
・伏線の提示・変奏・回収がF-IDで追跡できているか

⑤ ベースラインとの整合
・キャラクターのベースライン（普段の反応）からの逸脱が明示されているか
""",
    },
}


def load_latest_output(skill_num, novel_type: str) -> tuple:
    """該当スキルの最新出力ファイルを読み込む"""
    import os as _os
    key = "3-5" if skill_num in [3, 4, 5] else skill_num
    if key not in CHECK_DEFINITIONS:
        return None, ""

    defn = CHECK_DEFINITIONS[key]
    output_dir = BASE_DIR / "output" / defn["output_dir"]
    if not output_dir.exists():
        return None, ""

    # summaryファイルを優先、なければ最新ファイル
    pattern = defn["pattern"].replace("*", f"*{novel_type}*")
    files = sorted(output_dir.glob(pattern), key=lambda f: _os.path.getmtime(f), reverse=True)
    if not files:
        # patternを緩める
        files = sorted(output_dir.glob("*.md"), key=lambda f: _os.path.getmtime(f), reverse=True)

    if not files:
        return None, ""

    # 複数ファイルの場合は最新3つを結合
    combined = ""
    for f in files[:3]:
        combined += f.read_text(encoding="utf-8")[:1500] + "\n\n---\n\n"

    return files[0], combined


# ステップ番号→出力ディレクトリのマッピング
STEP_OUTPUTS = {
    1: ("s01_plot_twist",      "s02_*.md",            "S1どんでん返し設計"),
    2: ("s02_idea_decision",   "s02_*.md",             "S2アイデア・プロット"),
    "3-5": ("s03_s05_character", "s03_s05_character_*.md", "S3-5キャラクター設計"),
    6: ("s06_trauma",          "s08_*.md",             "S6トラウマ設計", 2500),
    7: ("s07_char_detail",     "s07_*_01_*.md",        "S7キャラクター詳細設計", 2000),
    8: ("s08_char_relation",   "s08_*.md",             "S8関係性設計"),
    9: ("s09_parallel_line",   "s09_*.md",             "S9並行線設計"),
    10: ("s10_plot_main",      "s10_*summary*.md",     "S10四幕構成プロット", 2000),
    11: ("s11_chapter_plot",   "s11_*.md",             "S11章構成プロット"),
    12: ("s12_scene_plot",     "s12_*_prologue_*.md",  "S12シーン構成", 2000),
}


def load_step_output(step_key, novel_type: str, max_chars: int = 800) -> str:
    """指定ステップの最新出力を読み込む"""
    if step_key not in STEP_OUTPUTS:
        return ""
    entry = STEP_OUTPUTS[step_key]
    dir_name, pattern, label = entry[0], entry[1], entry[2]
    # ステップ固有のmax_charsがあれば使用
    if len(entry) > 3:
        max_chars = entry[3]
    output_dir = BASE_DIR / "output" / dir_name
    if not output_dir.exists():
        return ""
    pat = pattern.replace("*", f"*{novel_type}*")
    files = sorted(output_dir.glob(pat), key=lambda f: os.path.getmtime(f), reverse=True)
    if not files:
        files = sorted(output_dir.glob("*.md"), key=lambda f: os.path.getmtime(f), reverse=True)
    if not files:
        return ""
    return f"【{label}】\n" + files[0].read_text(encoding="utf-8")[:max_chars]


def load_draft_text(novel_type: str, max_chars: int = 1500) -> str:
    """S13以降の文章ファイルが存在すれば読み込む"""
    import os as _os
    # S16→S15→S14→S13の順で優先
    search = [
        ("s16_revision",    f"s16_{novel_type}_*_complete_*.md"),
        ("s15_description", f"s15_{novel_type}_*_complete_*.md"),
        ("s14_dialogue",    f"s14_{novel_type}_*_complete_*.md"),
        ("s13_draft",       f"s13_{novel_type}_*_complete_*.md"),
    ]
    for dir_name, pattern in search:
        output_dir = BASE_DIR / "output" / dir_name
        if not output_dir.exists():
            continue
        files = sorted(output_dir.glob(pattern),
                       key=lambda f: _os.path.getmtime(f), reverse=True)
        if files:
            text = files[0].read_text(encoding="utf-8")[:max_chars]
            return f"【執筆済み文章（{dir_name}より）】\n{text}"
    return ""


def load_multiple_outputs(step_key: int, novel_type: str,
                          max_files: int = 4, max_chars_each: int = 500) -> str:
    """S10/S12の複数出力ファイルを読み込んでまとめる（ファイル間整合性チェック用）"""
    import os as _os
    if step_key == 10:
        output_dir = BASE_DIR / "output" / "s10_plot_main"
        patterns = [
            f"s10_{novel_type}_*_転_*.md",
            f"s10_{novel_type}_*_結_*.md",
            f"s10_{novel_type}_*_ミッド_*.md",
            f"s10_{novel_type}_*_承後半_*.md",
            f"s10_{novel_type}_*_承前半_*.md",
            f"s10_{novel_type}_*_非日常_*.md",
            f"s10_{novel_type}_*_起_*.md",
            f"s10_{novel_type}_*_プロローグ_*.md",
        ]
        label = "S10四幕構成プロット"
    elif step_key == 12:
        output_dir = BASE_DIR / "output" / "s12_scene_plot"
        patterns = [
            f"s12_{novel_type}_*_prologue_*.md",
            f"s12_{novel_type}_*_ch1_*.md",
            f"s12_{novel_type}_*_ch2_5_*.md",
            f"s12_{novel_type}_*_ch6_8_*.md",
            f"s12_{novel_type}_*_ch9_10_*.md",
            f"s12_{novel_type}_*_epilogue_*.md",
        ]
        label = "S12シーン構成"
    else:
        return ""

    if not output_dir.exists():
        return ""

    texts = []
    for pattern in patterns[:max_files]:
        files = sorted(output_dir.glob(pattern),
                       key=lambda f: _os.path.getmtime(f), reverse=True)
        if files:
            text = files[0].read_text(encoding="utf-8")[:max_chars_each]
            section = files[0].stem.split("_")[3] if len(files[0].stem.split("_")) > 3 else "?"
            texts.append(f"--- {section} ---\n{text}")

    if not texts:
        return ""

    return f"【{label}（{len(texts)}ファイル）】\n" + "\n\n".join(texts)


def run_check(skill_num, novel_type: str, config: dict) -> dict:
    """指定スキルの累積整合性チェックを実行（S1〜現スキルまで全出力を参照）"""
    key = "3-5" if skill_num in [3, 4, 5] else skill_num
    if key not in CHECK_DEFINITIONS:
        print(f"  [INFO] スキル{skill_num}のチェック定義なし（スキップ）")
        return {"passed": True, "notes": ""}

    defn = CHECK_DEFINITIONS[key]
    skill_label = defn["name"]
    print(f"\n  ── {skill_label}（累積チェック：S1〜S{skill_num}）──")

    # チェック対象を絞る：
    # S2チェック → S1+S2
    # S3-5チェック → S2+S3-5
    # S6以降 → S2（プロット参照）+ 現在のステップのみ
    all_steps_text = ""
    max_step = key

    if key == 2:
        ref_steps = [1, 2]
    elif key in ["3-5"]:
        ref_steps = [2, "3-5"]
    else:
        # S6以降：S2プロット + 現在のステップ
        ref_steps = [2, key]

    draft_text = ""
    # S10/S12は自身の複数ファイルを読み込んで整合性チェック
    multi_text = ""
    if key in [10, 12]:
        multi_text = load_multiple_outputs(key, novel_type)
        if multi_text:
            print(f"  [INFO] S{key}の複数ファイルを読み込み（ファイル間整合性チェック）")

    for step in ref_steps:
        chars = 2000 if step == max_step else 800
        step_text = load_step_output(step, novel_type, max_chars=chars)
        if step_text:
            all_steps_text += step_text + "\n\n"

    if multi_text:
        all_steps_text = multi_text + "\n\n" + all_steps_text

    if not all_steps_text:
        print(f"  [WARNING] 出力ファイルが見つかりません（スキップ）")
        return {"passed": True, "notes": "ファイルなし"}

    print("  チェック中（Claude Sonnet）...")

    prompt = (
        f"以下の出力が整合しているか確認してください（S{skill_num}が中心）。\n\n"
        + defn["criteria"] + "\n\n"
        + "【参照出力】\n"
        + all_steps_text[:3500] + "\n\n"
        "【出力形式】\n"
        "## 判定\n"
        "✅ 合格 または ⚠️ 要確認 または ❌ 問題あり\n\n"
        "## ステップ別チェック結果\n"
        "| ステップ | 判定 | コメント |\n"
        "|---------|------|---------|\n"
        "（各ステップについて記載）\n\n"
        "## 整合性の問題\n"
        "（ステップ間で矛盾・不整合がある場合のみ）\n\n"
        "## 修正提案\n"
        "（問題がある場合のみ。どのステップを修正すべきか）\n\n"
        "## 総評（2〜3行）"
    )

    result = call_claude_sonnet(prompt)

    # 判定を抽出
    passed = "❌" not in result
    has_warning = "⚠️" in result

    # 結果を表示
    print("\n" + "="*50)
    print(result)
    print("="*50)

    # ファイル保存
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    check_dir = BASE_DIR / "output" / "auto_checks"
    check_dir.mkdir(parents=True, exist_ok=True)
    check_path = check_dir / f"check_skill{skill_num}_{novel_type}_{timestamp}.md"
    with open(check_path, "w", encoding="utf-8") as f:
        f.write(f"# {defn['name']} チェック結果\n実行日時：{timestamp}\n\n---\n\n{result}")
    print(f"\n  [OK] チェック結果保存: {check_path.name}")

    return {
        "passed": passed,
        "warning": has_warning,
        "result": result,
        "path": str(check_path),
    }


def prompt_continue(skill_num: int, check_result: dict) -> bool:
    """チェック結果を表示して続行確認"""
    if check_result.get("passed") and not check_result.get("warning"):
        print("\n  ✅ チェック合格 → 次のステップに進みます")
        return True

    if check_result.get("warning"):
        print("\n  ⚠️  要確認事項があります")
    else:
        print("\n  ❌  問題が検出されました")

    print("\n  続行しますか？")
    print("  [Enter]  → そのまま続行")
    print("  [r]      → 現ステップを再実行")
    print("  [q]      → 中断")

    try:
        ans = input("  > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""

    if ans == "q":
        print("  パイプラインを中断します")
        return False
    elif ans == "r":
        print(f"  スキル{skill_num}を再実行してください：")
        print(f"  python run_pipeline.py --skill {skill_num} --type [type]")
        return False
    else:
        print("  続行します")
        return True
