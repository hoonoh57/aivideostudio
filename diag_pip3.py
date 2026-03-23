# D:\aivideostudio\diag_pip3.py
"""_run_export 내 PIP 관련 코드 확인"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
lines = ep.read_text(encoding="utf-8").split('\n')

# _run_export 시작~끝 범위 찾기
start = end = -1
for i, line in enumerate(lines):
    if 'def _run_export' in line:
        start = i
    if start > 0 and i > start and line.strip().startswith('def ') and '_run_export' not in line:
        end = i
        break

print(f"_run_export: lines {start+1}-{end+1}")
print()

# pip_layers 참조 찾기
print("=== pip references in _run_export ===")
for i in range(start, end):
    if 'pip' in lines[i].lower():
        print(f"  {i+1}: {lines[i].rstrip()}")

# concat_out ~ audio mix 사이 출력
print("\n=== around concat_out ===")
for i in range(start, end):
    if 'concat_out' in lines[i] or 'Step 3' in lines[i] or 'Step 4' in lines[i] or 'pip_layer' in lines[i]:
        # 전후 5줄
        for j in range(max(start, i-2), min(end, i+8)):
            print(f"  {j+1}: {lines[j].rstrip()}")
        print()
