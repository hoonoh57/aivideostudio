"""Thumbnail / filmstrip engine for timeline clips.

Uses FFmpeg to generate a horizontal sprite sheet (tile Nx1) of evenly-spaced
frames.  The sprite sheet is loaded once; paintEvent slices it into individual
frames that tile across the clip width.

Reference implementation: KDE Kdenlive ClipThumbs.qml
Research basis: Torralba (MIT), "How many pixels make an image?" – 32×32 color
pixels yield 80 % scene-recognition accuracy.
"""
from __future__ import annotations
import os, subprocess, tempfile, threading, hashlib
from pathlib import Path
from loguru import logger

from PyQt6.QtCore import QThread, pyqtSignal

# ── thread-safe cache ──────────────────────────────────────────────
_cache: dict[str, str] = {}
_lock = threading.Lock()


def _cache_key(path: str, n_frames: int, frame_h: int) -> str:
    return f"{path}|{n_frames}|{frame_h}"


def extract_filmstrip_sync(
    video_path: str,
    duration: float,
    num_frames: int,
    frame_height: int,
    ffmpeg: str = "ffmpeg",
) -> str | None:
    """Generate a Nx1 horizontal sprite sheet.  Returns path to PNG or None."""
    key = _cache_key(video_path, num_frames, frame_height)
    with _lock:
        if key in _cache and os.path.isfile(_cache[key]):
            return _cache[key]

    if duration <= 0 or num_frames < 1:
        return None

    fps_val = num_frames / duration          # evenly-spaced
    fps_str = f"{fps_val:.6f}"

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = tmp.name
        tmp.close()

        cmd = [
            ffmpeg, "-y",
            "-i", video_path,
            "-frames:v", "1",
            "-vf", f"fps={fps_str},scale=-2:{frame_height},tile={num_frames}x1",
            "-q:v", "3",
            tmp_path,
        ]
        logger.debug(f"Filmstrip cmd: {' '.join(cmd)}")
        subprocess.run(cmd, timeout=30, capture_output=True)

        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 200:
            with _lock:
                _cache[key] = tmp_path
            logger.info(
                f"Filmstrip OK: {os.path.basename(video_path)} "
                f"frames={num_frames} h={frame_height}"
            )
            return tmp_path
        else:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
            return None
    except Exception as e:
        logger.error(f"Filmstrip error: {e}")
        return None


def extract_thumbnail_sync(
    video_path: str, time: float, ffmpeg: str = "ffmpeg"
) -> str | None:
    """Single-frame extraction (legacy, used for non-video assets)."""
    key = f"single|{video_path}|{time:.2f}"
    with _lock:
        if key in _cache and os.path.isfile(_cache[key]):
            return _cache[key]
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        cmd = [
            ffmpeg, "-y", "-ss", str(time),
            "-i", video_path,
            "-vframes", "1",
            "-vf", "scale=200:-2",
            "-q:v", "3",
            tmp_path,
        ]
        subprocess.run(cmd, timeout=10, capture_output=True)
        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 100:
            with _lock:
                _cache[key] = tmp_path
            return tmp_path
        else:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
            return None
    except Exception:
        return None


class FilmstripWorkerThread(QThread):
    """Background thread – emits (clip_id, sprite_path, num_frames)."""
    filmstrip_ready = pyqtSignal(int, str, int)

    def __init__(self, clip_id, video_path, duration, num_frames, frame_height, ffmpeg):
        super().__init__()
        self.clip_id = clip_id
        self.video_path = video_path
        self.duration = duration
        self.num_frames = num_frames
        self.frame_height = frame_height
        self.ffmpeg = ffmpeg

    def run(self):
        result = extract_filmstrip_sync(
            self.video_path, self.duration,
            self.num_frames, self.frame_height,
            self.ffmpeg,
        )
        if result:
            self.filmstrip_ready.emit(self.clip_id, result, self.num_frames)


class ThumbnailEngine:
    """Compatibility wrapper."""
    def __init__(self, ffmpeg_path="ffmpeg"):
        self._ffmpeg = ffmpeg_path

    def generate(self, path, time=0):
        return extract_thumbnail_sync(path, time, self._ffmpeg)


def clear_cache():
    with _lock:
        for p in _cache.values():
            try:
                os.unlink(p)
            except OSError:
                pass
        _cache.clear()
