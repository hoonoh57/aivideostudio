# D:\aivideostudio\diag_zone2.py
"""Zone Bar 렌더링 조건 상세 진단"""
from pathlib import Path

tp = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
lines = tp.read_text(encoding="utf-8").splitlines()

# TimelineCanvas의 paintEvent (line 1192 부근) 전체 출력
print("=" * 70)
print("TimelineCanvas.paintEvent 전체 (line 1192~)")
print("=" * 70)

# paintEvent 시작부터 다음 def까지
in_paint = False
start = None
for i, l in enumerate(lines):
    if i >= 1190 and "def paintEvent" in l:
        start = i
        in_paint = True
        continue
    if in_paint and l.strip().startswith("def ") and "paintEvent" not in l:
        end = i
        break
else:
    end = len(lines)

if start:
    for i in range(start, end):
        print(f"{i+1:5d}: {lines[i].rstrip()}")

# _track_y 메서드 확인 (Zone Bar 오프셋)
print("\n" + "=" * 70)
print("_track_y 메서드")
print("=" * 70)
for i, l in enumerate(lines):
    if "def _track_y" in l:
        for j in range(i, min(i+10, len(lines))):
            print(f"{j+1:5d}: {lines[j].rstrip()}")
        break

# mousePressEvent에서 zone 처리 부분
print("\n" + "=" * 70)
print("mousePressEvent - zone 관련")
print("=" * 70)
in_press = False
for i, l in enumerate(lines):
    if "def mousePressEvent" in l and i > 470:  # TimelineCanvas의 것
        in_press = True
        start_mp = i
    if in_press and i > start_mp and l.strip().startswith("def "):
        end_mp = i
        break
else:
    end_mp = len(lines) if in_press else 0

if in_press:
    for i in range(start_mp, end_mp):
        if "zone" in lines[i].lower() or i == start_mp:
            # 주변 3줄씩도 출력
            for j in range(max(start_mp, i-1), min(end_mp, i+4)):
                marker = ">>>" if j == i else "   "
                print(f"{marker} {j+1:5d}: {lines[j].rstrip()[:120]}")
            print()

# _total_duration 확인
print("=" * 70)
print("_total_duration 초기화/설정")
print("=" * 70)
for i, l in enumerate(lines):
    if "_total_duration" in l:
        print(f"  {i+1:5d}: {l.rstrip()[:120]}")

# _zone_visible 사용처
print("\n" + "=" * 70)
print("_zone_visible 사용처")
print("=" * 70)
for i, l in enumerate(lines):
    if "_zone_visible" in l:
        print(f"  {i+1:5d}: {l.rstrip()[:120]}")
