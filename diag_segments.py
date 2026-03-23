# D:\aivideostudio\diag_segments.py
"""실제 세그먼트 데이터 확인"""
from pathlib import Path

# 1. playback_engine의 get_ordered_video_segments 확인
base = Path(r"D:\aivideostudio\aivideostudio")

# engines 폴더에서 playback_engine 찾기
print("=" * 70)
print("1. get_ordered_video_segments 메서드 찾기")
print("=" * 70)

for py_file in sorted(base.rglob("*.py")):
    src = py_file.read_text(encoding="utf-8", errors="replace")
    if "get_ordered_video_segments" in src:
        lines = src.splitlines()
        for i, l in enumerate(lines):
            if "def get_ordered_video_segments" in l:
                print(f"\n  File: {py_file}")
                indent = len(l) - len(l.lstrip())
                end = len(lines)
                for j in range(i+1, len(lines)):
                    if lines[j].strip() and lines[j].strip().startswith("def ") and \
                       (len(lines[j]) - len(lines[j].lstrip())) <= indent:
                        end = j
                        break
                for k in range(i, end):
                    print(f"  {k+1:5d}: {lines[k].rstrip()}")

# 2. get_ordered_audio_segments도 확인
print("\n" + "=" * 70)
print("2. get_ordered_audio_segments 메서드")
print("=" * 70)

for py_file in sorted(base.rglob("*.py")):
    src = py_file.read_text(encoding="utf-8", errors="replace")
    if "get_ordered_audio_segments" in src:
        lines = src.splitlines()
        for i, l in enumerate(lines):
            if "def get_ordered_audio_segments" in l:
                print(f"\n  File: {py_file}")
                indent = len(l) - len(l.lstrip())
                end = len(lines)
                for j in range(i+1, len(lines)):
                    if lines[j].strip() and lines[j].strip().startswith("def ") and \
                       (len(lines[j]) - len(lines[j].lstrip())) <= indent:
                        end = j
                        break
                for k in range(i, end):
                    print(f"  {k+1:5d}: {lines[k].rstrip()}")

# 3. 타임라인에서 현재 트랙/클립 정보를 runtime에서 출력하는 코드
# export_panel._on_export에 디버그 추가 대신, 세그먼트 수집 로직만 따로 실행
print("\n" + "=" * 70)
print("3. _run_export의 video_segs 처리 - duration 계산 확인")
print("=" * 70)
print("""
  문제 핵심: Segment 1이 실패
  Segment 0: -ss 0.0 -t 8.0 → 성공
  Segment 1: no packets → in_point가 소스 길이 초과 or duration=0
  
  _run_export line 305: dur = seg["timeline_end"] - seg["timeline_start"]
  _run_export line 319: in_pt = seg.get("in_point", 0)
  → in_pt가 소스보다 크거나 dur=0이면 FFmpeg 실패
""")

# 4. V Video 2 트랙의 클립이 어떻게 세그먼트화되는지
# timeline_panel에서 tracks 구조 확인
tp = base / "gui" / "panels" / "timeline_panel.py"
lines = tp.read_text(encoding="utf-8").splitlines()
print("=" * 70)
print("4. 트랙 초기화 / 기본 트랙 구조")
print("=" * 70)
for i, l in enumerate(lines):
    if "tracks" in l.lower() and ("append" in l or "= [" in l or "default" in l.lower()):
        if i > 470:  # TimelineCanvas 영역
            print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 5. 세그먼트에 duration=0 방지 필터가 있는지
ep = base / "gui" / "panels" / "export_panel.py"
ep_lines = ep.read_text(encoding="utf-8").splitlines()
print("\n" + "=" * 70)
print("5. duration 유효성 검사 유무")
print("=" * 70)
for i, l in enumerate(ep_lines):
    if "dur" in l.lower() and ("< 0" in l or "<= 0" in l or "> 0" in l or "skip" in l.lower()):
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")

if not any("dur" in l.lower() and ("< 0" in l or "<= 0" in l) for l in ep_lines):
    print("  [WARNING] duration 유효성 검사 없음 - 0초 세그먼트가 FFmpeg로 전달될 수 있음!")
