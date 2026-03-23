# D:\aivideostudio\diag_serialize.py
"""_serialize_project 전체 확인"""
from pathlib import Path

MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
lines = MW.read_text(encoding="utf-8").split('\n')

print("=== _serialize_project 전체 ===")
for i, line in enumerate(lines):
    if 'def _serialize_project' in line:
        for j in range(i, min(len(lines), i+50)):
            print(f"  {j+1:4d} | {lines[j]}")
            if j > i and lines[j].strip().startswith('def ') and '_serialize_project' not in lines[j]:
                break
        break

# _do_open에서 clip 복원 부분
print("\n=== _do_open: clip 복원 ===")
for i, line in enumerate(lines):
    if 'def _do_open' in line:
        for j in range(i, min(len(lines), i+80)):
            print(f"  {j+1:4d} | {lines[j]}")
            if j > i + 5 and lines[j].strip().startswith('def '):
                break
        break
