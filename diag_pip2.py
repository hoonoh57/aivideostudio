# D:\aivideostudio\diag_pip2.py
"""Export PIP 코드 확인"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
src = ep.read_text(encoding="utf-8")
lines = src.split('\n')

print(f"Total lines: {len(lines)}")

# 1. pip 관련 코드 검색
print("\n=== pip references ===")
for i, line in enumerate(lines, 1):
    if 'pip' in line.lower() and ('layer' in line.lower() or 'overlay' in line.lower() or 'pip_' in line.lower()):
        print(f"  {i}: {line.strip()[:100]}")

# 2. _on_export 메서드 출력
print("\n=== _on_export method ===")
in_method = False
for i, line in enumerate(lines, 1):
    if 'def _on_export' in line:
        in_method = True
    if in_method:
        print(f"  {i}: {line.rstrip()}")
        if in_method and i > 1 and line.strip().startswith('def ') and '_on_export' not in line:
            break

# 3. _run_export signature
print("\n=== _run_export signature ===")
for i, line in enumerate(lines, 1):
    if 'def _run_export' in line:
        print(f"  {i}: {line.strip()[:120]}")

# 4. _apply_pip_overlay 존재 여부
print(f"\n_apply_pip_overlay exists: {'def _apply_pip_overlay' in src}")
print(f"pip_layers in _on_export: {'pip_layers' in src}")
print(f"get_pip_video_layers in export: {'get_pip_video_layers' in src}")
