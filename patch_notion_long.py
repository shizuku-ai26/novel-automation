# -*- coding: utf-8 -*-
"""Notion長文保存を一括修正 - ファイルごとに正確な置換を実施"""
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

def add_import(text, filename):
    """notion_create_page_longをimportに追加"""
    if "notion_create_page_long" in text:
        return text
    for old, new in [
        ("    notion_create_page, save_output, txt",
         "    notion_create_page, notion_create_page_long, save_output, txt"),
        ("    notion_create_page, save_output,",
         "    notion_create_page, notion_create_page_long, save_output,"),
        ("notion_create_page, save_output, txt",
         "notion_create_page, notion_create_page_long, save_output, txt"),
    ]:
        if old in text:
            print(f"    import追加OK")
            return text.replace(old, new, 1)
    print(f"    [WARNING] import追加失敗")
    return text

PATCHES = {
    "s07_char_relation.py": [
        (
            '        children = [\n'
            '            {"object": "block", "type": "heading_2",\n'
            '             "heading_2": {"rich_text": txt("相関図（全体）")}},\n'
            '            {"object": "block", "type": "paragraph",\n'
            '             "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '        ]\n'
            '        if len(result) > 2000:\n'
            '            children.append({\n'
            '                "object": "block", "type": "paragraph",\n'
            '                "paragraph": {"rich_text": txt(result[2000:4000])}\n'
            '            })\n'
            '        notion_create_page(token, char_db, {\n'
            '            "名前": {"title": txt(f"{timestamp}_関係性設計")},\n'
            '            "スキル": {"rich_text": txt("⑦キャラクター関係性設計")},\n'
            '            "小説タイプ": {"rich_text": txt(novel_type)},\n'
            '            "ステータス": {"select": {"name": "未使用"}},\n'
            '        }, children)',
            'notion_create_page_long(token, char_db, {\n'
            '            "名前": {"title": txt(f"{timestamp}_関係性設計")},\n'
            '            "スキル": {"rich_text": txt("⑦キャラクター関係性設計")},\n'
            '            "小説タイプ": {"rich_text": txt(novel_type)},\n'
            '            "ステータス": {"select": {"name": "未使用"}},\n'
            '        }, "相関図（全体）", result)',
        ),
    ],
    "s08_plot_twist.py": [
        (
            '        }, [\n'
            '            {"object": "block", "type": "heading_2",\n'
            '             "heading_2": {"rich_text": txt("どんでん返し設計")}},\n'
            '            {"object": "block", "type": "paragraph",\n'
            '             "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '        ])',
            '        }, "どんでん返し設計", result)',
        ),
        (
            'notion_create_page(token, plot_db,',
            'notion_create_page_long(token, plot_db,',
        ),
    ],
    "s09_parallel_line.py": [
        (
            '        }, [\n'
            '            {"object": "block", "type": "heading_2",\n'
            '             "heading_2": {"rich_text": txt("並行線設計")}},\n'
            '            {"object": "block", "type": "paragraph",\n'
            '             "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '        ])',
            '        }, "並行線設計", result)',
        ),
        (
            'notion_create_page(token, plot_db,',
            'notion_create_page_long(token, plot_db,',
        ),
    ],
    "s10_plot_main.py": [
        (
            '            }, [\n'
            '                {"object": "block", "type": "heading_2",\n'
            '                 "heading_2": {"rich_text": txt(p[\'name\'])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[2000:4000])}},\n'
            '            ])',
            "            }, p['name'], result)",
        ),
        (
            '            notion_create_page(token, plot_db,',
            '            notion_create_page_long(token, plot_db,',
        ),
    ],
    "s11_chapter_plot.py": [
        (
            '            }, [\n'
            '                {"object": "block", "type": "heading_2",\n'
            '                 "heading_2": {"rich_text": txt(ch[\'name\'])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[2000:4000])}},\n'
            '            ])',
            "            }, ch['name'], result)",
        ),
        (
            '            notion_create_page(token, plot_db,',
            '            notion_create_page_long(token, plot_db,',
        ),
    ],
    "s12_scene_plot.py": [
        (
            '            }, [\n'
            '                {"object": "block", "type": "heading_2",\n'
            '                 "heading_2": {"rich_text": txt(section[\'name\'])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[:2000])}},\n'
            '                {"object": "block", "type": "paragraph",\n'
            '                 "paragraph": {"rich_text": txt(result[2000:4000])}},\n'
            '            ])',
            "            }, section['name'], result)",
        ),
        (
            '            notion_create_page(token, scene_db,',
            '            notion_create_page_long(token, scene_db,',
        ),
    ],
}

def main():
    print("=" * 50)
    print("Notion長文保存 一括パッチ（正確版）")
    print("=" * 50)

    ok, failed = [], []

    for filename, replacements in PATCHES.items():
        path = SKILLS_DIR / filename
        if not path.exists():
            print(f"  [SKIP] ファイルなし: {filename}")
            continue

        text = path.read_text(encoding="utf-8")
        original = text

        # import追加
        text = add_import(text, filename)

        # 各置換を適用
        for old, new in replacements:
            if old in text:
                text = text.replace(old, new, 1)
                print(f"  [OK] 置換成功: {filename} ({old[:40].strip()}...)")
            else:
                print(f"  [?] パターン未マッチ: {filename} ({old[:40].strip()}...)")

        if text != original:
            path.write_text(text, encoding="utf-8")
            ok.append(filename)
            print(f"  --> {filename} 保存完了")
        else:
            failed.append(filename)
            print(f"  [WARNING] 変更なし: {filename}")

    print(f"\n完了: {len(ok)}件 / 未変更: {len(failed)}件")
    print("=" * 50)

if __name__ == "__main__":
    main()
