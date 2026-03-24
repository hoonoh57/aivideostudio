# D:\aivideostudio\diag_restore.py
"""프로젝트 열기 시 clip_data 복원 흐름 확인"""
from pathlib import Path

MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
lines = MW.read_text(encoding="utf-8").splitlines()

# Find _do_open method and show clip restoration
print("=== _do_open: clip 복원 부분 ===")
in_do_open = False
for i, line in enumerate(lines):
    if 'def _do_open' in line:
        in_do_open = True
    if in_do_open:
        if any(kw in line for kw in ['clip_data', 'subtitle_style', 'style_locked', 'pip', 'cd[', 'clip[']):
            print(f"  {i+1:4d} | {line.rstrip()}")
    if in_do_open and i > 0 and 'def ' in line and '_do_open' not in line:
        break

# Also check _serialize_project for style_locked
print("\n=== _serialize_project: style_locked ===")
for i, line in enumerate(lines):
    if 'style_locked' in line:
        print(f"  {i+1:4d} | {line.rstrip()}")

# Check the actual .avs file
print("\n=== test.avs: style_locked 확인 ===")
import json
avs = Path(r"C:\Users\haoru\Downloads\test.avs")
if avs.exists():
    d = json.load(avs.open(encoding="utf-8"))
    for t in d.get("tracks", []):
        if t.get("type") == "subtitle":
            locked_count = sum(1 for c in t["clips"] if c.get("style_locked"))
            total = len(t["clips"])
            print(f"  Track '{t.get('name')}': {locked_count}/{total} clips locked")
            # Show first locked clip
            for c in t["clips"]:
                if c.get("style_locked"):
                    print(f"    Example: {c.get('subtitle_text','')[:30]}... style_locked={c['style_locked']}")
                    break
