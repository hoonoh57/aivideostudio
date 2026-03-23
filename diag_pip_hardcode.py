# D:\aivideostudio\diag_pip_hardcode.py
"""PIP 하드코딩(트랙 번호 기반) 로직 전수 조사"""
from pathlib import Path

files = {
    "playback_engine": Path(r"D:\aivideostudio\aivideostudio\core\playback_engine.py"),
    "export_panel": Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py"),
    "timeline_panel": Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py"),
    "preview_panel": Path(r"D:\aivideostudio\aivideostudio\gui\panels\preview_panel.py"),
}

bad_patterns = [
    "track_idx",           # 트랙 인덱스 기반 판별
    "track_index",
    "video 1",
    "video 2",
    "Video 1",
    "Video 2",
    'idx == 0',
    'idx == 1',
    'idx > 0',
    'idx >= 1',
    "first video track",
    "first_video",
    "overlay track",
    "base track",
    "break  # Only first",
]

for name, path in files.items():
    if not path.exists():
        print(f"\n=== {name}: FILE NOT FOUND ===")
        continue
    lines = path.read_text(encoding="utf-8").split('\n')
    print(f"\n=== {name} ({len(lines)} lines) ===")
    
    found = False
    for i, line in enumerate(lines):
        for pat in bad_patterns:
            if pat.lower() in line.lower():
                print(f"  ⚠ Line {i+1}: {line.rstrip()}")
                found = True
                break
    
    # PIP 판별 로직 확인
    for i, line in enumerate(lines):
        if 'get_pip_video_layers' in line or 'get_ordered_video_segments' in line:
            print(f"  📌 Line {i+1}: {line.rstrip()}")
            # 전후 10줄
            for j in range(max(0, i-2), min(len(lines), i+15)):
                print(f"      {j+1}: {lines[j].rstrip()}")
            print()
    
    if not found:
        print("  ✅ No hard-coded track references found")
