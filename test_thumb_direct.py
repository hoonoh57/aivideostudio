from aivideostudio.engines.thumbnail_engine import extract_thumbnail_sync

path = r"D:\aivideostudio\timeline_export.mp4"
ffmpeg = r"D:\ffmpeg\bin\ffmpeg.exe"

print(f"Testing: {path}")
print(f"FFmpeg: {ffmpeg}")

result = extract_thumbnail_sync(path, 0.0, ffmpeg)
print(f"Result at 0.0s: {result}")

result2 = extract_thumbnail_sync(path, 7.0, ffmpeg)
print(f"Result at 7.0s: {result2}")

if result:
    import os
    print(f"File size: {os.path.getsize(result)} bytes")