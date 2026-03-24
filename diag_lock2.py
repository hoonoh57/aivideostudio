# D:\aivideostudio\diag_lock2.py
"""OK(edit) 핸들러 전체 흐름 확인"""
from pathlib import Path

TP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
tp_lines = TP.read_text(encoding="utf-8").splitlines()

# Find _edit_subtitle_text method
print("=== _edit_subtitle_text: edit action 처리 ===")
for i, line in enumerate(tp_lines):
    if '_edit_subtitle_text' in line and 'def ' in line:
        # Print from here to next def or end
        for j in range(i, min(len(tp_lines), i + 80)):
            print(f"  {j+1:4d} | {tp_lines[j].rstrip()}")
        print("\n... (first 80 lines of method)")
        break

# Also check what happens after dialog.exec
print("\n=== dialog result handling ===")
for i, line in enumerate(tp_lines):
    if 'dialog.exec' in line or 'dlg.exec' in line:
        if 930 < i < 1100:
            for j in range(max(0, i-2), min(len(tp_lines), i+40)):
                print(f"  {j+1:4d} | {tp_lines[j].rstrip()}")
            print()

# Check style_locked in paintEvent
print("\n=== paintEvent: style_locked ===")
for i, line in enumerate(tp_lines):
    if 'style_locked' in line and i < 250:
        print(f"  {i+1:4d} | {tp_lines[i].rstrip()}")
