"""Thumbnail extraction engine using FFmpeg.
Thread-safe: ffmpeg runs in QThread, QPixmap created only on main thread.
"""
import subprocess
import tempfile
import os
import threading
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap
from loguru import logger

_cache = {}
_lock = threading.Lock()


def _cache_key(path, time_sec):
    return (str(path), round(time_sec, 2))


def extract_thumbnail_sync(file_path, time_sec, ffmpeg="ffmpeg"):
    """Extract a frame to a temp file. Returns temp file path or None."""
    path = str(file_path)
    key = _cache_key(path, time_sec)
    with _lock:
        if key in _cache:
            return _cache[key]
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        cmd = [
            ffmpeg, "-y", "-ss", f"{time_sec:.3f}",
            "-i", path, "-vframes", "1",
            "-vf", "scale=200:-2", "-q:v", "3",
            "-loglevel", "error", tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and os.path.getsize(tmp_path) > 100:
            with _lock:
                _cache[key] = tmp_path
            return tmp_path
        else:
            try: os.unlink(tmp_path)
            except OSError: pass
            return None
    except subprocess.TimeoutExpired:
        logger.debug(f"Thumbnail timeout: {Path(path).name}@{time_sec:.1f}s")
        return None
    except FileNotFoundError:
        logger.warning("ffmpeg not found - thumbnails disabled")
        return None
    except Exception as e:
        logger.debug(f"Thumbnail extract error: {e}")
        return None


class ThumbnailWorkerThread(QThread):
    """QThread that extracts start/end thumbnails and emits file paths."""
    # Signal: (clip_id, start_path_or_empty, end_path_or_empty)
    thumbnails_ready = pyqtSignal(int, str, str)

    def __init__(self, clip_id, video_path, in_point, out_point, ffmpeg="ffmpeg"):
        super().__init__()
        self._clip_id = clip_id
        self._video_path = str(video_path)
        self._in_point = in_point
        self._out_point = out_point
        self._ffmpeg = ffmpeg or "ffmpeg"

    def run(self):
        """Runs in background thread - no Qt GUI objects here."""
        end_time = max(self._in_point + 0.1, self._out_point - 0.1)
        p1 = extract_thumbnail_sync(self._video_path, self._in_point, self._ffmpeg)
        p2 = extract_thumbnail_sync(self._video_path, end_time, self._ffmpeg)
        self.thumbnails_ready.emit(
            self._clip_id,
            p1 or "",
            p2 or ""
        )


class ThumbnailEngine:
    """Generates thumbnail image files for video assets (used by main_window)."""
    def __init__(self, ffmpeg_path="ffmpeg"):
        self._ffmpeg = ffmpeg_path or "ffmpeg"

    def generate(self, video_path, time_sec=1.0):
        path = str(video_path)
        if not os.path.isfile(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                      ".tiff", ".tif", ".webp", ".svg")
        if ext in image_exts:
            return path
        return extract_thumbnail_sync(path, time_sec, self._ffmpeg)


def clear_cache():
    with _lock:
        for fp in _cache.values():
            try: os.unlink(fp)
            except OSError: pass
        _cache.clear()
    logger.info("Thumbnail cache cleared")
