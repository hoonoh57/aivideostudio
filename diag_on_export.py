# D:\aivideostudio\diag_on_export.py
"""_on_export 메서드 전체 출력"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
lines = ep.read_text(encoding="utf-8").splitlines()

# _on_export 전체
for i, l in enumerate(lines):
    if "def _on_export" in l:
        start = i
        indent = len(l) - len(l.lstrip())
        for j in range(i+1, len(lines)):
            if lines[j].strip().startswith("def ") and \
               (len(lines[j]) - len(lines[j].lstrip())) <= indent:
                end = j
                break
        else:
            end = len(lines)
        
        print(f"_on_export: lines {start+1} ~ {end}")
        print("=" * 70)
        for k in range(start, end):
            print(f"{k+1:5d}: {lines[k].rstrip()}")
        break

# _run_export 처음 30줄도 출력 (segment logging 부분)
print("\n" + "=" * 70)
print("_run_export 처음 70줄:")
print("=" * 70)
for i, l in enumerate(lines):
    if "def _run_export" in l:
        for k in range(i, min(i+70, len(lines))):
            print(f"{k+1:5d}: {lines[k].rstrip()}")
        break
