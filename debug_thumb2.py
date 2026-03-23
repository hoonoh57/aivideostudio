"""Debug: test thumbnail extraction directly."""
import subprocess
import os

# 1. Check ffmpeg exists
try:
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    print(f"ffmpeg: OK ({r.stdout[:50]})")
except FileNotFoundError:
    print("ffmpeg: NOT FOUND!")
except Exception as e:
    print(f"ffmpeg error: {e}")

# 2. Test extraction on actual video file
video = r"D:\aivideostudio\timeline_export.mp4"
if not os.path.isfile(video):
    # Try to find any mp4
    for root, dirs, files in os.walk(r"D:\aivideostudio"):
        for f in files:
            if f.endswith(".mp4"):
                video = os.path.join(root, f)
                break
        break

print(f"\nTest video: {video}")
print(f"Exists: {os.path.isfile(video)}")

if os.path.isfile(video):
    from aivideostudio.engines.thumbnail_engine import extract_thumbnail_sync
    result = extract_thumbnail_sync(video, 1.0)
    print(f"extract_thumbnail_sync result: {result}")
    if result:
        print(f"  File exists: {os.path.isfile(result)}")
        print(f"  File size: {os.path.getsize(result)}")

# 3. Check if _request_thumbnails is called
print("\n=== Check timeline_panel.py ===")
lines = open("aivideostudio/gui/panels/timeline_panel.py", encoding="utf-8").readlines()
for i, l in enumerate(lines):
    if "_request_thumbnails" in l:
        print(f"  {i+1}: {l.rstrip()}")
for i, l in enumerate(lines):
    if "extract_pair_async" in l or "_extract_thumb_pair" in l:
        print(f"  {i+1}: {l.rstrip()}")
