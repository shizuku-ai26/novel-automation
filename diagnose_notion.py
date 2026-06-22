# -*- coding: utf-8 -*-
"""診断：各スキルファイルのNotion保存パターンを確認"""
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

for f in sorted(SKILLS_DIR.glob("s*.py")):
    text = f.read_text(encoding="utf-8")
    if "result[:2000]" in text or "result[2000:4000]" in text:
        print(f"\n{'='*50}")
        print(f"FILE: {f.name}")
        print('='*50)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'result[:2000]' in line or 'result[2000:4000]' in line:
                start = max(0, i-5)
                end = min(len(lines), i+5)
                for j in range(start, end):
                    marker = ">>>" if j == i else "   "
                    print(f"{marker} {j+1:4}: {lines[j]}")
