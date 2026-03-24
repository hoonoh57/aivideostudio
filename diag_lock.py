# D:\aivideostudio\diag_lock.py
"""잠금 저장 흐름 진단"""
from pathlib import Path

SED = Path(r"D:\aivideostudio\aivideostudio\gui\dialogs\subtitle_edit_dialog.py")
TP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")

# 1) Dialog: OK handler에서 locked 포함하는지
sed_lines = SED.read_text(encoding="utf-8").splitlines()
print("=== subtitle_edit_dialog.py ===")
for i, line in enumerate(sed_lines):
    if any(kw in line for kw in ['result_data', 'result_action', 'chk_lock', 'locked', 'style_locked']):
        print(f"  {i+1:4d} | {line.rstrip()}")

# 2) Dialog: _on_split, _on_merge, accept 에서 locked 전달?
print("\n--- accept / OK 관련 ---")
for i, line in enumerate(sed_lines):
    if 'accept()' in line or 'def accept' in line:
        start = max(0, i-5)
        for j in range(start, min(len(sed_lines), i+3)):
            print(f"  {j+1:4d} | {sed_lines[j].rstrip()}")
        print()

# 3) Timeline: OK action에서 style_locked 저장?
tp_lines = TP.read_text(encoding="utf-8").splitlines()
print("=== timeline_panel.py: _edit_subtitle_text ===")
for i, line in enumerate(tp_lines):
    if any(kw in line for kw in ['style_locked', 'locked', 'action == "ok"', 'action == "split"']):
        if 920 < i < 1050:
            print(f"  {i+1:4d} | {line.rstrip()}")

# 4) 현재 OK result_data에 locked가 있는지?
print("\n--- result_data 생성 위치 ---")
in_on_split = False
for i, line in enumerate(sed_lines):
    if 'def _on_split' in line:
        in_on_split = True
    if 'def _on_merge' in line:
        in_on_split = False
    if in_on_split and 'result_data' in line:
        print(f"  {i+1:4d} | {line.rstrip()}")
