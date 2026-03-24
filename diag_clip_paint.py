# D:\aivideostudio\diag_clip_paint.py
"""ClipWidget paintEvent 확인 — 스타일 표식 추가 위치 파악"""
from pathlib import Path

TP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
lines = TP.read_text(encoding="utf-8").split('\n')

# ClipWidget의 paintEvent
print("=== ClipWidget.paintEvent ===")
in_clip = False
for i, line in enumerate(lines):
    if 'class ClipWidget' in line:
        in_clip = True
    if in_clip and 'class TimelineCanvas' in line:
        break
    if in_clip and 'def paintEvent' in line:
        for j in range(i, min(len(lines), i+60)):
            print(f"  {j+1:4d} | {lines[j]}")
            if j > i and lines[j].strip().startswith('def '):
                break
        break

# subtitle 클립 관련 표시 로직
print("\n=== subtitle label/draw 관련 ===")
for i, line in enumerate(lines):
    if 'subtitle' in line.lower() and ('draw' in line.lower() or 'paint' in line.lower() or 'label' in line.lower()):
        print(f"  {i+1:4d} | {line.rstrip()}")
