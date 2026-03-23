# D:\aivideostudio\diag_pip.py
"""PIP 관련 코드 위치 확인"""
from pathlib import Path

tp = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
lines = tp.read_text(encoding="utf-8").split('\n')

print(f"Total lines: {len(lines)}")
print()

# 1. _edit_pip_settings 검색
print("=== _edit_pip_settings ===")
for i, line in enumerate(lines, 1):
    if '_edit_pip_settings' in line:
        print(f"  Line {i}: {line.strip()[:100]}")

# 2. act_pip 검색
print("\n=== act_pip ===")
for i, line in enumerate(lines, 1):
    if 'act_pip' in line:
        print(f"  Line {i}: {line.strip()[:100]}")

# 3. Line 485-495 출력 (act_pip handler 근처)
print("\n=== Lines 483-495 ===")
for i in range(482, min(495, len(lines))):
    print(f"  {i+1:4d} | {lines[i]}")

# 4. _edit_pip_settings 메서드 전체 출력
print("\n=== _edit_pip_settings method ===")
in_method = False
for i, line in enumerate(lines, 1):
    if 'def _edit_pip_settings' in line:
        in_method = True
    if in_method:
        print(f"  {i:4d} | {line}")
        if in_method and i > 1 and line.strip() and not line.startswith(' '):
            break
        if in_method and 'def ' in line and '_edit_pip_settings' not in line:
            break
