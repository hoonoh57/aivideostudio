# D:\aivideostudio\diag_export2.py
"""Export 세그먼트 수집 + 범위 필터 진단"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
lines = ep.read_text(encoding="utf-8").splitlines()

# 1. _get_video_segments 전체
print("=" * 70)
print("_get_video_segments 메서드")
print("=" * 70)
in_method = False
indent = 0
for i, l in enumerate(lines):
    if "def _get_video_segments" in l:
        in_method = True
        indent = len(l) - len(l.lstrip())
        start = i
    elif in_method and l.strip().startswith("def ") and (len(l) - len(l.lstrip())) <= indent:
        end = i
        break
else:
    end = len(lines) if in_method else 0

if in_method:
    for i in range(start, end):
        print(f"{i+1:5d}: {lines[i].rstrip()}")

# 2. _get_audio_segments
print("\n" + "=" * 70)
print("_get_audio_segments 메서드 (있다면)")
print("=" * 70)
in_method = False
for i, l in enumerate(lines):
    if "def _get_audio_segments" in l:
        in_method = True
        indent = len(l) - len(l.lstrip())
        start = i
    elif in_method and l.strip().startswith("def ") and (len(l) - len(l.lstrip())) <= indent:
        end = i
        break
else:
    end = len(lines) if in_method else 0
if in_method:
    for i in range(start, end):
        print(f"{i+1:5d}: {lines[i].rstrip()}")
else:
    print("  (not found)")

# 3. export 버튼 핸들러 (세그먼트 수집 → _run_export 호출 부분)
print("\n" + "=" * 70)
print("Export 버튼 핸들러 (_on_export / _start_export)")
print("=" * 70)
for kw in ["def _on_export", "def _start_export", "def export_timeline"]:
    for i, l in enumerate(lines):
        if kw in l:
            in_method = True
            indent = len(l) - len(l.lstrip())
            start = i
            for j in range(i+1, len(lines)):
                if lines[j].strip().startswith("def ") and (len(lines[j]) - len(lines[j].lstrip())) <= indent:
                    end = j
                    break
            else:
                end = len(lines)
            for k in range(start, end):
                print(f"{k+1:5d}: {lines[k].rstrip()}")
            print()
            break

# 4. Range filter 적용 부분
print("\n" + "=" * 70)
print("Range filter 적용 코드 검색")
print("=" * 70)
for i, l in enumerate(lines):
    ll = l.lower()
    if any(k in ll for k in ["export_range", "filter", "trim", "range_start", "range_end", "z_in", "z_out"]):
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")
