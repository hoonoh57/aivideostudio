# D:\aivideostudio\diag_pe_query.py
"""playback_engine.py query() 메서드의 video 처리 로직 확인"""
from pathlib import Path

PE = Path(r"D:\aivideostudio\aivideostudio\core\playback_engine.py")
lines = PE.read_text(encoding="utf-8").split('\n')

print(f"Total lines: {len(lines)}")

# query 메서드 전체 출력 (video 부분)
print("\n=== query() video handling (lines 82-105) ===")
for i in range(81, min(110, len(lines))):
    print(f"  {i+1:4d} | {lines[i]}")

# get_ordered_video_segments 전체
print("\n=== get_ordered_video_segments ===")
for i, line in enumerate(lines):
    if 'def get_ordered_video_segments' in line:
        for j in range(i, min(len(lines), i+35)):
            print(f"  {j+1:4d} | {lines[j]}")
            if j > i and lines[j].strip().startswith('def '):
                break
        break

# get_pip_video_layers 전체
print("\n=== get_pip_video_layers ===")
for i, line in enumerate(lines):
    if 'def get_pip_video_layers' in line:
        for j in range(i, min(len(lines), i+40)):
            print(f"  {j+1:4d} | {lines[j]}")
            if j > i and lines[j].strip().startswith('def ') and 'get_pip_video_layers' not in lines[j]:
                break
        break
