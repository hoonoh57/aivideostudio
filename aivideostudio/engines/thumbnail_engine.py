"""Thumbnail extraction engine using FFmpeg.
Extracts frames at specific timestamps and caches them as QPixmap.
"""
import subprocess
import hashlib
import threading
from pathlib import Path
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
from loguru import logger

_cache = {}  # key: (path, time_sec, height) -> QPixmap
_lock = threading.Lock()


def _cache_key(path, time_sec, height):
    return (str(path), round(time_sec, 2), height)


def extract_thumbnail(file_path, time_sec, height=76, callback=None):
    """Extract a single frame thumbnail.
    
    Args:
        file_path: video file path
        time_sec: timestamp in seconds
        height: desired thumbnail height in pixels
        callback: optional callable(QPixmap) called on success
    
    Returns QPixmap if cached, otherwise starts async extraction and returns None.
    """
    path = str(file_path)
    key = _cache_key(path, time_sec, height)

    with _lock:
        if key in _cache:
            px = _cache[key]
            if callback:
                callback(px)
            return px

    # Start async extraction
    t = threading.Thread(target=_extract_worker,
                         args=(path, time_sec, height, key, callback),
                         daemon=True)
    t.start()
    return None


def _extract_worker(path, time_sec, height, key, callback):
    """Worker thread: run ffmpeg to extract a frame."""
    try:
        # Calculate width maintaining aspect ratio (assume 16:9 as default)
        width = int(height * 16 / 9)
        # Ensure even dimensions for ffmpeg
        width = width + (width % 2)
        height = height + (height % 2)

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{time_sec:.3f}",
            "-i", path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-loglevel", "error",
            "pipe:1"
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode != 0:
            logger.debug(f"Thumbnail ffmpeg error for {Path(path).name}@{time_sec:.1f}s")
            return

        raw = result.stdout
        expected = width * height * 3
        if len(raw) < expected:
            logger.debug(f"Thumbnail incomplete: {len(raw)}/{expected} bytes")
            return

        # Create QImage from raw RGB data
        img = QImage(raw[:expected], width, height, width * 3,
                     QImage.Format.Format_RGB888)
        if img.isNull():
            return

        pixmap = QPixmap.fromImage(img)
        if pixmap.isNull():
            return

        with _lock:
            _cache[key] = pixmap

        if callback:
            callback(pixmap)

    except subprocess.TimeoutExpired:
        logger.debug(f"Thumbnail timeout: {Path(path).name}@{time_sec:.1f}s")
    except FileNotFoundError:
        logger.warning("ffmpeg not found - thumbnails disabled")
    except Exception as e:
        logger.debug(f"Thumbnail error: {e}")


def extract_pair(file_path, in_point, out_point, height=76, callback=None):
    """Extract start and end thumbnails for a clip.
    
    Args:
        file_path: video file path
        in_point: clip in point (seconds)
        out_point: clip out point (seconds)
        height: desired height
        callback: callable(start_pixmap, end_pixmap) called when both ready
    
    Returns (start_px, end_px) tuple of cached pixmaps or (None, None).
    """
    results = [None, None]
    done = [0]  # mutable counter

    def on_start(px):
        results[0] = px
        done[0] += 1
        if done[0] == 2 and callback:
            try:
                callback(results[0], results[1])
            except RuntimeError:
                pass

    def on_end(px):
        results[1] = px
        done[0] += 1
        if done[0] == 2 and callback:
            try:
                callback(results[0], results[1])
            except RuntimeError:
                pass

    # Ensure end point is at least slightly before actual end to get a valid frame
    end_time = max(in_point + 0.1, out_point - 0.1)

    start_px = extract_thumbnail(file_path, in_point, height, on_start)
    end_px = extract_thumbnail(file_path, end_time, height, on_end)

    if start_px and end_px:
        if callback:
            callback(start_px, end_px)
        return start_px, end_px

    return None, None


def clear_cache():
    """Clear all cached thumbnails."""
    with _lock:
        _cache.clear()
    logger.info("Thumbnail cache cleared")


class ThumbnailEngine:
    """Generates thumbnail image files for video assets (used by main_window)."""

    def __init__(self, ffmpeg_path="ffmpeg"):
        self._ffmpeg = ffmpeg_path or "ffmpeg"

    def generate(self, video_path, time_sec=1.0):
        """Generate a thumbnail file and return its path, or None on failure."""
        import tempfile, os
        path = str(video_path)
        if not os.path.isfile(path):
            return None

        ext = os.path.splitext(path)[1].lower()
        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                      ".tiff", ".tif", ".webp", ".svg")
        if ext in image_exts:
            return path  # image itself is the thumbnail

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp_path = tmp.name
            tmp.close()

            cmd = [
                self._ffmpeg, "-y",
                "-ss", f"{time_sec:.2f}",
                "-i", path,
                "-vframes", "1",
                "-vf", "scale=160:90:force_original_aspect_ratio=decrease",
                "-q:v", "5",
                "-loglevel", "error",
                tmp_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and os.path.getsize(tmp_path) > 100:
                return tmp_path
            else:
                os.unlink(tmp_path)
                return None
        except Exception as e:
            logger.debug(f"ThumbnailEngine.generate error: {e}")
            return None
