"""Thumbnail extraction engine using FFmpeg.
Extracts frames at specific timestamps, saves to temp files, loads as QPixmap.
Thread-safe: ffmpeg runs in background, QPixmap created on main thread.
"""
import subprocess
import threading
import tempfile
import os
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from loguru import logger


class _ThumbSignal(QObject):
    """Helper to deliver thumbnail callback on main thread."""
    deliver = pyqtSignal(object, object, object)

    def __init__(self):
        super().__init__()
        self.deliver.connect(self._on_deliver)

    def _on_deliver(self, p1, p2, cb):
        _deliver(p1, p2, cb)

_thumb_signal = None

def _get_signal():
    global _thumb_signal
    if _thumb_signal is None:
        _thumb_signal = _ThumbSignal()
    return _thumb_signal

_cache = {}  # key: (path, time_sec) -> file_path (str)
_pixmap_cache = {}  # key: (path, time_sec) -> QPixmap
_lock = threading.Lock()


def _cache_key(path, time_sec):
    return (str(path), round(time_sec, 2))


def extract_thumbnail_sync(file_path, time_sec, ffmpeg="ffmpeg"):
    """Extract a frame to a temp file. Returns temp file path or None.
    Safe to call from any thread (no Qt objects created).
    """
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
            ffmpeg, "-y",
            "-ss", f"{time_sec:.3f}",
            "-i", path,
            "-vframes", "1",
            "-vf", "scale=200:-2",
            "-q:v", "3",
            "-loglevel", "error",
            tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode == 0 and os.path.getsize(tmp_path) > 100:
            with _lock:
                _cache[key] = tmp_path
            return tmp_path
        else:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
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


def extract_pair_async(file_path, in_point, out_point, callback, ffmpeg="ffmpeg"):
    """Extract start/end thumbnails in background thread.
    callback(start_path, end_path) is scheduled on main thread via QTimer.
    """
    path = str(file_path)
    end_time = max(in_point + 0.1, out_point - 0.1)
    ff = ffmpeg or "ffmpeg"

    def worker():
        p1 = extract_thumbnail_sync(path, in_point, ff)
        p2 = extract_thumbnail_sync(path, end_time, ff)
        # Schedule callback on main thread
        _get_signal().deliver.emit(p1, p2, callback)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def _deliver(path1, path2, callback):
    """Called on main thread: load QPixmaps and invoke callback."""
    px1 = None
    px2 = None
    if path1:
        px1 = QPixmap(path1)
        if px1.isNull():
            px1 = None
    if path2:
        px2 = QPixmap(path2)
        if px2.isNull():
            px2 = None
    if px1 or px2:
        try:
            callback(px1, px2)
        except RuntimeError:
            pass


# Legacy API compatibility
def extract_pair(file_path, in_point, out_point, height=76, callback=None, ffmpeg="ffmpeg"):
    """Compatibility wrapper."""
    if callback:
        extract_pair_async(file_path, in_point, out_point, callback, ffmpeg)
    return None, None


def clear_cache():
    """Clear all cached thumbnails."""
    with _lock:
        for fp in _cache.values():
            try:
                os.unlink(fp)
            except OSError:
                pass
        _cache.clear()
        _pixmap_cache.clear()
    logger.info("Thumbnail cache cleared")


class ThumbnailEngine:
    """Generates thumbnail image files for video assets (used by main_window)."""

    def __init__(self, ffmpeg_path="ffmpeg"):
        self._ffmpeg = ffmpeg_path or "ffmpeg"

    def generate(self, video_path, time_sec=1.0):
        """Generate a thumbnail file and return its path, or None on failure."""
        path = str(video_path)
        if not os.path.isfile(path):
            return None

        ext = os.path.splitext(path)[1].lower()
        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                      ".tiff", ".tif", ".webp", ".svg")
        if ext in image_exts:
            return path

        return extract_thumbnail_sync(path, time_sec, self._ffmpeg)
