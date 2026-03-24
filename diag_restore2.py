# D:\aivideostudio\diag_restore2.py
"""_do_open과 _serialize_project 전체 확인"""
from pathlib import Path

MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
lines = MW.read_text(encoding="utf-8").splitlines()

# 1) _serialize_project 전체
print("=== _serialize_project ===")
for i, line in enumerate(lines):
    if 'def _serialize_project' in line:
        for j in range(i, min(len(lines), i+60)):
            print(f"  {j+1:4d} | {lines[j].rstrip()}")
        break

# 2) _do_open: clip 복원 전체
print("\n=== _do_open: clip restore section ===")
for i, line in enumerate(lines):
    if 'def _do_open' in line:
        for j in range(i, min(len(lines), i+120)):
            print(f"  {j+1:4d} | {lines[j].rstrip()}")
        break
