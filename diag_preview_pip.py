# D:\aivideostudio\diag_preview_pip.py
"""Preview PIP 지원 현황 진단"""
from pathlib import Path

pp = Path(r"D:\aivideostudio\aivideostudio\gui\panels\preview_panel.py")
lines = pp.read_text(encoding="utf-8").split('\n')

print(f"Total lines: {len(lines)}")
print()

# PIP 관련 코드 검색
print("=== PIP references in preview_panel ===")
for i, line in enumerate(lines):
    if 'pip' in line.lower() or 'overlay' in line.lower() or 'video_layers' in line.lower():
        print(f"  {i+1}: {line.rstrip()}")

# mpv 관련 - 두 번째 mpv 인스턴스 또는 overlay 방법
print("\n=== mpv player instances ===")
for i, line in enumerate(lines):
    if 'mpv' in line.lower() and ('create' in line.lower() or 'player' in line.lower() or '_mpv' in line.lower()):
        print(f"  {i+1}: {line.rstrip()}")

# _sync 또는 load_file 관련
print("\n=== load / sync methods ===")
for i, line in enumerate(lines):
    if 'def ' in line and ('load' in line.lower() or 'sync' in line.lower() or 'play' in line.lower()):
        print(f"  {i+1}: {line.rstrip()}")

# query 사용
print("\n=== engine.query usage ===")
for i, line in enumerate(lines):
    if 'query' in line and 'engine' in line.lower():
        print(f"  {i+1}: {line.rstrip()}")

# QLabel / QWidget overlay 가능성
print("\n=== QLabel / widget overlay ===")
for i, line in enumerate(lines):
    if 'QLabel' in line or 'QVideoWidget' in line or 'overlay' in line.lower():
        print(f"  {i+1}: {line.rstrip()}")
