# D:\aivideostudio\diag_export.py
"""Export 세그먼트 생성 로직 진단"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
src = ep.read_text(encoding="utf-8")
lines = src.splitlines()

# 1. _run_export 메서드 전체 출력
print("=" * 70)
print("export_panel.py - _run_export / segment 생성 로직")
print("=" * 70)

in_method = False
method_indent = 0
start = end = 0
for i, l in enumerate(lines):
    if "def _run_export" in l:
        start = i
        in_method = True
        method_indent = len(l) - len(l.lstrip())
        continue
    if in_method and l.strip() and not l.strip().startswith("#"):
        curr_indent = len(l) - len(l.lstrip())
        if l.strip().startswith("def ") and curr_indent <= method_indent:
            end = i
            break
if not end:
    end = len(lines)

for i in range(start, end):
    print(f"{i+1:5d}: {lines[i].rstrip()}")

# 2. segment 관련 다른 메서드들
print("\n" + "=" * 70)
print("segment / gap / concat 관련 메서드")
print("=" * 70)
keywords = ["_collect_segments", "_build_segments", "segment", "gap", "concat", 
            "black_gap", "_get_export_range", "filter_segments", "trim"]
for kw in keywords:
    for i, l in enumerate(lines):
        if kw in l.lower() and ("def " in l or "# " in l.strip()[:2]):
            print(f"  {i+1:5d}: {l.rstrip()[:120]}")

# 3. _get_export_range 전체
print("\n" + "=" * 70)
print("_get_export_range 메서드")
print("=" * 70)
for i, l in enumerate(lines):
    if "def _get_export_range" in l:
        for j in range(i, min(i+20, len(lines))):
            print(f"{j+1:5d}: {lines[j].rstrip()}")
            if j > i and lines[j].strip() and lines[j].strip().startswith("def "):
                break
        break

# 4. 세그먼트 FFmpeg 명령 생성 부분
print("\n" + "=" * 70)
print("FFmpeg 명령 생성 (segment / part_ 관련)")
print("=" * 70)
for i, l in enumerate(lines):
    if "part_" in l or "ffmpeg" in l.lower() or "-ss" in l or "Segment" in l:
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")
