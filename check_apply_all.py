# D:\aivideostudio\check_apply_all.py
"""_on_apply_all 메서드 위치와 인덴트 확인"""
from pathlib import Path

SED = Path(r"D:\aivideostudio\aivideostudio\gui\dialogs\subtitle_edit_dialog.py")
lines = SED.read_text(encoding="utf-8").split('\n')

print(f"Total lines: {len(lines)}")

for i, line in enumerate(lines):
    if '_on_apply_all' in line or '_check_multiple_styles' in line:
        print(f"\n  Found at line {i+1}:")
        for j in range(max(0, i-1), min(len(lines), i+10)):
            vis = lines[j].replace('\t', '→→→→')
            print(f"  {j+1:4d} | {vis}")
