# D:\aivideostudio\diag_zone.py
"""Zone Bar 관련 코드 진단"""
from pathlib import Path

BASE = Path(r"D:\aivideostudio\aivideostudio\gui\panels")

# 1. timeline_panel.py에서 zone 관련 코드 검색
tp = BASE / "timeline_panel.py"
src = tp.read_text(encoding="utf-8")
lines = src.splitlines()

print("=" * 60)
print("1. timeline_panel.py - Zone 관련 코드 검색")
print("=" * 60)

keywords = [
    "zone_bar", "ZONE_BAR", "_zone_in", "_zone_out", "_zone_enabled",
    "zone_height", "ZONE_HEIGHT", "Zone Bar", "zone bar",
    "Key_I", "Key_O", "set_zone_in", "set_zone_out",
    "paintEvent", "drawRect", "fillRect", "zone"
]

found_any = False
for kw in keywords:
    matching = [(i+1, l.rstrip()) for i, l in enumerate(lines) if kw in l]
    if matching:
        found_any = True
        print(f"\n  '{kw}' found in {len(matching)} lines:")
        for num, txt in matching[:5]:
            print(f"    {num:5d}: {txt[:120]}")
        if len(matching) > 5:
            print(f"    ... and {len(matching)-5} more")

if not found_any:
    print("  [WARNING] Zone 관련 코드가 전혀 없습니다!")

# 2. paintEvent 전체 내용 확인
print("\n" + "=" * 60)
print("2. paintEvent 메서드 범위")
print("=" * 60)

in_paint = False
paint_start = None
paint_end = None
for i, l in enumerate(lines):
    if "def paintEvent" in l:
        paint_start = i + 1
        in_paint = True
    elif in_paint and l.strip() and not l.startswith(" ") and not l.startswith("\t"):
        paint_end = i
        in_paint = False
        break
    elif in_paint and l.strip().startswith("def ") and "paintEvent" not in l:
        paint_end = i
        break

if paint_start:
    if not paint_end:
        paint_end = min(paint_start + 100, len(lines))
    print(f"  paintEvent: lines {paint_start} ~ {paint_end}")
    print(f"  paintEvent 길이: {paint_end - paint_start} lines")
    # 처음 30줄과 마지막 20줄 출력
    pe_lines = lines[paint_start-1:paint_end]
    print("\n  --- 처음 30줄 ---")
    for j, l in enumerate(pe_lines[:30]):
        print(f"    {paint_start+j:5d}: {l.rstrip()[:120]}")
    if len(pe_lines) > 50:
        print(f"\n  --- ... 중간 생략 ({len(pe_lines)-50} lines) ... ---")
    print("\n  --- 마지막 20줄 ---")
    for j, l in enumerate(pe_lines[-20:]):
        print(f"    {paint_end-20+j+1:5d}: {l.rstrip()[:120]}")
else:
    print("  [WARNING] paintEvent를 찾을 수 없습니다!")

# 3. TimelineCanvas vs TimelinePanel 클래스 구조
print("\n" + "=" * 60)
print("3. 클래스 정의")
print("=" * 60)
for i, l in enumerate(lines):
    if l.strip().startswith("class ") and ("Timeline" in l or "Canvas" in l):
        print(f"  {i+1:5d}: {l.rstrip()}")

# 4. __init__에서 zone 변수 초기화 확인
print("\n" + "=" * 60)
print("4. __init__ 에서 zone 변수 초기화")
print("=" * 60)
in_init = False
for i, l in enumerate(lines):
    if "def __init__" in l:
        in_init = True
    elif in_init and l.strip().startswith("def "):
        in_init = False
    if in_init and "zone" in l.lower():
        print(f"  {i+1:5d}: {l.rstrip()}")

# 5. export_panel.py - set_timeline_canvas 확인
print("\n" + "=" * 60)
print("5. export_panel.py - set_timeline_canvas")
print("=" * 60)
ep = BASE / "export_panel.py"
ep_src = ep.read_text(encoding="utf-8")
ep_lines = ep_src.splitlines()
for i, l in enumerate(ep_lines):
    if "timeline_canvas" in l.lower() or "set_timeline" in l.lower():
        print(f"  {i+1:5d}: {l.rstrip()[:120]}")

# 6. main_window.py - timeline canvas 연결
print("\n" + "=" * 60)
print("6. main_window.py - canvas 연결")
print("=" * 60)
mw = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
mw_src = mw.read_text(encoding="utf-8")
for i, l in enumerate(mw_src.splitlines()):
    if "timeline_canvas" in l.lower() or "set_timeline_canvas" in l.lower() or ".canvas" in l.lower():
        print(f"  {i+1:5d}: {l.rstrip()[:120]}")

print("\n" + "=" * 60)
print("7. 파일 크기 확인")
print("=" * 60)
print(f"  timeline_panel.py: {len(lines)} lines, {len(src)} bytes")
print(f"  export_panel.py:   {len(ep_lines)} lines, {len(ep_src)} bytes")
