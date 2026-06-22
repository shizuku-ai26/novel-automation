# -*- coding: utf-8 -*-
"""
import_text.py：手動修正テキストをs13出力として登録するスクリプト
使い方：
  1. 修正したテキストファイルを NOVEL_AUTOMATION/input/import/ に置く
     ファイル名は 01_修正版.txt / prologue_修正版.txt 形式
  2. python import_text.py --list         # ファイル一覧確認
  3. python import_text.py --file-index 1 # 番号で選択してインポート
  4. 表示されるコマンドでs14を実行
"""

from pathlib import Path
from datetime import datetime

BASE_DIR   = Path(__file__).parent
IMPORT_DIR = BASE_DIR / "input" / "import"
S13_DIR    = BASE_DIR / "output" / "s13_draft"

# 短編：ファイル番号プレフィックス → (section_key, name)
NUM_TO_SECTION_SHORT = {
    "01":       ("ch1",       "起プロット（第1章）"),
    "02":       ("ch1_final", "非日常転換ポイント（第1章最終）"),
    "03":       ("ch2_5",     "承前半プロット（第2〜5章）"),
    "04":       ("ch5_final", "ミッドポイント（第5章最終）"),
    "05":       ("ch6_8",     "承後半プロット（第6〜8章）"),
    "06":       ("ch8_final", "転プロット（第8章最終）"),
    "07":       ("ch9_10",    "結プロット（第9〜10章）"),
    "prologue": ("prologue",  "プロローグ"),
    "epilogue": ("epilogue",  "エピローグ"),
}


def detect_section(filename: str) -> tuple:
    """ファイル名からセクションキーと番号を自動判定"""
    stem = Path(filename).stem.lower()

    for prefix, (key, name) in NUM_TO_SECTION_SHORT.items():
        if stem.startswith(prefix):
            # ファイル名のプレフィックス部分をそのまま番号として使用
            num = prefix.zfill(2)  # 01, 02, ... / prologue / epilogue
            return key, name, num

    return None, None, None


def list_files() -> list:
    """importフォルダのファイル一覧を表示"""
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        list(IMPORT_DIR.glob("*.txt")) + list(IMPORT_DIR.glob("*.md"))
    )
    if not files:
        print(f"\n  importフォルダにファイルがありません。")
        print(f"  以下のフォルダに .txt / .md ファイルを置いてください：")
        print(f"  {IMPORT_DIR}\n")
        return []

    print(f"\n  importフォルダのファイル一覧：")
    for i, f in enumerate(files, 1):
        key, name, num = detect_section(f.name)
        if key:
            print(f"    [{i}] {f.name}  →  {name}（{key}）")
        else:
            print(f"    [{i}] {f.name}  →  （セクション未判定）")
    return files


def import_file(file_index: int, novel_type: str = "short"):
    """選択したファイルをs13出力として登録"""
    files = list_files()
    if not files:
        return

    if file_index < 1 or file_index > len(files):
        print(f"  [ERROR] 番号 {file_index} は範囲外です（1〜{len(files)}）")
        return

    target = files[file_index - 1]
    key, name, num = detect_section(target.name)

    if not key:
        print(f"  [ERROR] ファイル名からセクションを判定できませんでした: {target.name}")
        print(f"  ファイル名を 01_xxx.txt / prologue_xxx.txt 形式にしてください。")
        return

    # テキスト読み込み
    content = target.read_text(encoding="utf-8")

    # ▼シーンマーカーがなければ自動付与
    if "▼シーン" not in content:
        content = "▼シーン1\n\n" + content
        print(f"  [INFO] ▼シーン1マーカーを自動付与しました")

    # 出力ファイル名：s13_short_01_ch1_imported_yyyymmdd_hhmm.md
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_name = f"s13_{novel_type}_{num}_{key}_{timestamp}.md"
    out_path = S13_DIR / out_name
    S13_DIR.mkdir(parents=True, exist_ok=True)

    header = (
        f"# 初版文章（インポート）：{name}\n"
        f"実行日時：{timestamp}\n"
        f"インポート元：{target.name}\n"
        f"小説タイプ：{novel_type}\n\n---\n\n"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + content)

    print(f"\n  [OK] インポート完了!")
    print(f"  登録ファイル: {out_name}")
    print(f"  セクション  : {name}（{key}）")
    print(f"  文字数      : {len(content):,}文字")
    print(f"\n  次のステップ:")
    print(f"    python run_pipeline.py --skill 14 --type {novel_type} --section-name {key}")
    print(f"    python run_pipeline.py --skill 15 --type {novel_type} --section-name {key}")
    print(f"    python run_pipeline.py --skill 16 --type {novel_type} --section-name {key}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="手動修正テキストをs13出力として登録します"
    )
    parser.add_argument("--file-index", type=int, default=None,
                        help="インポートするファイルの番号（--listで確認）")
    parser.add_argument("--type", type=str, default="short",
                        help="小説タイプ（short/medium/long）")
    parser.add_argument("--list", action="store_true",
                        help="importフォルダのファイル一覧を表示")
    args = parser.parse_args()

    print("\n============================================================")
    print(" テキストインポートツール")
    print("============================================================")

    if args.list or args.file_index is None:
        list_files()
        if not args.list:
            print("\n  --file-index で番号を指定してください。")
            print("  例: python import_text.py --file-index 1")
        return

    import_file(args.file_index, args.type)


if __name__ == "__main__":
    main()
