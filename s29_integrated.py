# -*- coding: utf-8 -*-
"""
S29：統合出力スキル
呼び出し：python run_pipeline.py --skill 29 --type short

役割：
  S26〜S28の処理結果を統合して最終原稿と手動処理まとめを出力する。

出力①：統合原稿（integrated_draft）
  - S28の全9セクションを順番に結合
  - ▷キャラ名：ラベル（S26）を維持
  - 【★五感】マーカー（S27）を維持
  - モノローグ（S28）を維持

出力②：手動処理まとめリスト（manual_summary）
  - S26のmanual_list（三島→AIのべりすと）
  - S27のsudowrite_list（五感描写→Sudowrite）
  - S28のmanual_list（比喩→Sudowrite）
  を1ファイルに統合

次ステップ：S30（整合性チェック）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from common.utils import load_config, notion_create_page_long, txt
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "s29_integrated"

SECTIONS = [
    {"index": 0, "key": "prologue", "name": "プロローグ"},
    {"index": 1, "key": "ch1",      "name": "第1章"},
    {"index": 2, "key": "ch2_3",    "name": "第2〜3章"},
    {"index": 3, "key": "ch4_5",    "name": "第4〜5章"},
    {"index": 4, "key": "midpoint", "name": "ミッドポイント"},
    {"index": 5, "key": "ch6_7",    "name": "第6〜7章"},
    {"index": 6, "key": "turning",  "name": "転"},
    {"index": 7, "key": "ch9_10",   "name": "第9〜10章"},
    {"index": 8, "key": "epilogue", "name": "エピローグ"},
]

# 手動処理ツール対応表
MANUAL_TOOLS = {
    "s26": {
        "pattern": "s26_*_manual_list_*.md",
        "label":   "S26 セリフ強化 手動処理",
        "tools":   "三島→AIのべりすと（トリックスター・自由）",
    },
    "s27": {
        "pattern": "s27_*_sudowrite_list_*.md",
        "label":   "S27 情景描写 手動処理",
        "tools":   "五感描写→Sudowrite（Amplify / Sensory）",
    },
    "s28": {
        "pattern": "s28_*_manual_list_*.md",
        "label":   "S28 モノローグ強化 手動処理",
        "tools":   "比喩表現→Sudowrite（Prose Poem）",
    },
}


# ============================================================
# 本文ファイル読み込み
# ============================================================

def load_latest_body(novel_type: str, section_index: int) -> tuple:
    """S28 → S27 → S26 → S25の順で最新ファイルを読み込む"""
    base = Path(__file__).parent.parent / "output"

    for skill_dir, prefix in [
        ("s28_monologue",   "s28"),
        ("s27_description", "s27"),
        ("s26_dialogue",    "s26"),
        ("s25_rhythm",      "s25"),
    ]:
        files = sorted(
            (base / skill_dir).glob(
                f"{prefix}_{novel_type}_{section_index}_*.md"
            ),
            reverse=True
        )
        files = [f for f in files
                 if "manual" not in f.name and "sudowrite" not in f.name]
        if files:
            text = files[0].read_text(encoding="utf-8")
            body = text.split("---", 1)[-1].strip() if "---" in text else text
            return body, files[0].name

    return "", ""


# ============================================================
# 手動処理リスト読み込み
# ============================================================

def load_manual_lists(novel_type: str, section_index: int = None) -> dict:
    """S26・S27・S28の手動処理リストを読み込む（全セクション結合対応）"""
    base = Path(__file__).parent.parent / "output"
    results = {}

    skill_dirs = {
        "s26": ("s26_dialogue",    f"s26_{novel_type}_manual_list"),
        "s27": ("s27_description", f"s27_{novel_type}_sudowrite_list"),
        "s28": ("s28_monologue",   f"s28_{novel_type}_manual_list"),
    }

    for skill_key, (skill_dir, prefix) in skill_dirs.items():
        search_dir = base / skill_dir

        if section_index is not None:
            # 単一セクション：そのセクション番号のファイルを読み込む
            files = sorted(
                search_dir.glob(f"{prefix}_{section_index}_*.md"),
                reverse=True
            )
            if files:
                results[skill_key] = files[0].read_text(encoding="utf-8")
                print(f"    [手動リスト] {skill_key}: {files[0].name}")
            else:
                results[skill_key] = ""
        else:
            # 全セクション：section0〜8を順番に結合
            combined = []
            for sec_idx in range(len(SECTIONS)):
                files = sorted(
                    search_dir.glob(f"{prefix}_{sec_idx}_*.md"),
                    reverse=True
                )
                files = [f for f in files if "summary" not in f.name]
                if files:
                    combined.append(files[0].read_text(encoding="utf-8"))
                    print(f"    [手動リスト] {skill_key} sec{sec_idx}: {files[0].name}")
            # セクションファイルが1件もなければ旧形式フォールバック
            if not combined:
                files = sorted(
                    search_dir.glob(f"{prefix}_*.md"),
                    reverse=True
                )
                files = [f for f in files if "summary" not in f.name]
                if files:
                    combined.append(files[0].read_text(encoding="utf-8"))
                    print(f"    [手動リスト] {skill_key}: {files[0].name}（旧形式）")
            results[skill_key] = "\n\n".join(combined)

    return results


# ============================================================
# ★五感マーカー箇所の抽出
# ============================================================

MARKERS = {
    "【★五感】": "Sudowrite（Amplify / Sensory）",
    "【★比喩】": "Sudowrite（Prose Poem）",
    # 【★モノ】は三人称視点のため使用しない
}

def extract_all_markers(body: str, section_name: str) -> dict:
    """【★五感】【★比喩】【★モノ】マーカーの付いた行を種別ごとに抽出"""
    lines   = body.split("\n")
    results = {key: [] for key in MARKERS}

    for i, line in enumerate(lines):
        for marker in MARKERS:
            if marker in line:
                clean = line
                for m in MARKERS:
                    clean = clean.replace("　" + m, "").replace(m, "")
                clean = clean.strip()
                results[marker].append(
                    f"  行{i+1}: {clean[:60]}{'...' if len(clean)>60 else ''}"
                )
    return results


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

    targets = [SECTIONS[section_index]] if section_index is not None else SECTIONS

    print("\n[S29] 統合出力スキル 開始")
    print(f"  小説タイプ: {novel_type}")
    if section_index is not None:
        print(f"  対象セクション: {targets[0]['name']}")
    else:
        print(f"  処理: S28出力を統合 + 手動処理リストをまとめ")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── ① 統合原稿を作成 ────────────────────────
    print("\n  ① 本文統合中...")
    integrated_parts = []
    total_chars      = 0
    sense_summary    = []
    source_log       = []

    for section in targets:
        body, source_file = load_latest_body(novel_type, section["index"])
        if not body:
            print(f"    [WARN] {section['name']}: 入力ファイルなし → スキップ")
            continue

        char_count = len(body)
        total_chars += char_count
        source_log.append(f"  {section['name']}: {source_file}（{char_count:,}字）")
        print(f"    {section['name']}: {source_file}（{char_count:,}字）")

        # セクション区切りを追加
        integrated_parts.append(
            f"{'='*60}\n"
            f"【{section['name']}】\n"
            f"{'='*60}\n\n"
            f"{body}"
        )

        # ★マーカー箇所を抽出（五感・比喩・モノ）
        all_markers = extract_all_markers(body, section["name"])
        total_count = sum(len(v) for v in all_markers.values())
        if total_count > 0:
            block = f"\n■ {section['name']}\n"
            for marker, tool in MARKERS.items():
                lines_found = all_markers[marker]
                if lines_found:
                    block += f"  {marker} → {tool}（{len(lines_found)}箇所）\n"
                    block += "\n".join(lines_found) + "\n"
            sense_summary.append(block)

    integrated_body = "\n\n".join(integrated_parts)

    # 統合原稿ファイル保存
    sec_suffix = f"_{section_index}" if section_index is not None else ""
    draft_path = OUTPUT_DIR / f"s29_{novel_type}_integrated_draft{sec_suffix}_{timestamp}.md"
    draft_content = (
        f"# 統合原稿（S26〜S28処理済み）\n"
        f"実行日時：{timestamp}\n"
        f"総文字数：{total_chars:,}字\n\n"
        f"## ソースファイル\n"
        + "\n".join(source_log) + "\n\n"
        f"## 凡例\n"
        f"  ▷キャラ名：← 話者ラベル（S26付与・最終出力時は削除）\n"
        f"  【★五感】← 五感強化候補（Sudowrite処理後に削除）\n\n"
        f"---\n\n"
        f"{integrated_body}"
    )
    draft_path.write_text(draft_content, encoding="utf-8")
    print(f"\n  [OK] 統合原稿: {draft_path.name}（{total_chars:,}字）")

    # ── ② ★五感まとめリストを作成 ─────────────────
    sense_path = OUTPUT_DIR / f"s29_{novel_type}_sense_list{sec_suffix}_{timestamp}.md"
    sense_content = (
        f"# ★マーカー一覧（五感・比喩・モノ）\n"
        f"実行日時：{timestamp}\n\n"
        f"## マーカー凡例\n"
        f"  【★五感】 → Sudowrite（Amplify / Sensory）\n"
        f"  【★比喩】 → Sudowrite（Prose Poem）\n\n"
        f"処理完了後、各マーカーを削除してください。\n\n"
    )
    if sense_summary:
        sense_content += "\n".join(sense_summary)
    else:
        sense_content += "（五感マーカーなし）"
    sense_path.write_text(sense_content, encoding="utf-8")
    print(f"  [OK] ★五感リスト: {sense_path.name}")

    # ── ③ 手動処理まとめリストを作成 ─────────────
    print("\n  ③ 手動処理リスト統合中...")
    manual_lists = load_manual_lists(novel_type, section_index=section_index)

    manual_content = (
        f"# 手動処理まとめリスト（S26〜S28）\n"
        f"実行日時：{timestamp}\n\n"
        f"## 処理順序（推奨）\n"
        f"  1. 三島のセリフ → AIのべりすと（トリックスター・自由）\n"
        f"  2. 五感描写     → Sudowrite（Amplify / Sensory）\n"
        f"  3. 比喩表現     → Sudowrite（Prose Poem）\n\n"
        f"---\n\n"
    )

    for skill_key, info in MANUAL_TOOLS.items():
        manual_content += (
            f"{'='*60}\n"
            f"【{info['label']}】\n"
            f"ツール：{info['tools']}\n"
            f"{'='*60}\n\n"
        )
        if manual_lists.get(skill_key):
            # ヘッダー行を除いた本文のみ追加
            body_part = manual_lists[skill_key]
            if "---" in body_part:
                body_part = body_part.split("---", 1)[-1].strip()
            manual_content += body_part + "\n\n"
        else:
            manual_content += "（リストファイルなし）\n\n"

    manual_path = OUTPUT_DIR / f"s29_{novel_type}_manual_summary{sec_suffix}_{timestamp}.md"
    manual_path.write_text(manual_content, encoding="utf-8")
    print(f"  [OK] 手動処理まとめ: {manual_path.name}")

    # Notionに統合原稿を保存
    if plot_db:
        notion_create_page_long(token, plot_db, {
            "名前":       {"title": txt(f"{timestamp}_統合原稿")},
            "スキル":     {"rich_text": txt("S29_統合出力")},
            "小説タイプ": {"rich_text": txt(novel_type)},
            "ステータス": {"select": {"name": "手動処理待ち"}},
        }, "統合原稿", integrated_body[:5000])

    print(f"\n[S29] 完了")
    print(f"  総文字数: {total_chars:,}字")
    print(f"\n  ■ 出力ファイル")
    print(f"  統合原稿     : {draft_path.name}")
    print(f"  ★五感リスト  : {sense_path.name}")
    print(f"  手動処理まとめ: {manual_path.name}")
    print(f"\n  ■ 次のステップ")
    print(f"  1. 手動処理まとめを参照してGrok/AIのべりすと/Sudowrite/NovelAIで処理")
    print(f"  2. 手動処理完了後に統合原稿へ反映")
    print(f"  3. S30（整合性チェック）を実行")
    print(f"  コマンド例: python run_pipeline.py --skill 30 --type {novel_type}")

    return {
        "draft_path":  str(draft_path),
        "sense_path":  str(sense_path),
        "manual_path": str(manual_path),
        "total_chars": total_chars,
        "timestamp":   timestamp,
    }


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
