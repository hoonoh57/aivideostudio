import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from aivideostudio.engines.thumbnail_engine import extract_pair_async

app = QApplication(sys.argv)

path = r"D:\aivideostudio\timeline_export.mp4"
ffmpeg = r"D:\ffmpeg\bin\ffmpeg.exe"

def on_done(start_px, end_px):
    print(f"Callback received!")
    print(f"  start_px: {start_px} null={start_px.isNull() if start_px else 'N/A'}")
    print(f"  end_px: {end_px} null={end_px.isNull() if end_px else 'N/A'}")
    app.quit()

print(f"Calling extract_pair_async...")
extract_pair_async(path, 0.0, 8.0, on_done, ffmpeg)

# Timeout after 10 seconds
QTimer.singleShot(10000, lambda: (print("TIMEOUT: callback never called!"), app.quit()))

app.exec()
