"""Waveform Engine — extract audio peaks for timeline display."""
import json
import hashlib
import subprocess
import struct
from pathlib import Path
from loguru import logger

_CACHE_DIR = Path.home() / ".aivideostudio" / "waveform_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Target: ~2 peaks per pixel at 100 pps  roughly 200 peaks/sec
PEAKS_PER_SECOND = 200


def _cache_key(file_path: str) -> str:
    h = hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12]
    name = Path(file_path).stem[:20]
    return f"{name}_{h}"


def get_cached_peaks(file_path: str):
    """Return cached peak data or None."""
    key = _cache_key(file_path)
    cache_file = _CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return data.get("peaks", [])
        except Exception:
            pass
    return None


def generate_peaks(file_path: str, ffmpeg_path: str = "ffmpeg",
                   duration: float = 0.0) -> list:
    """Extract audio waveform peaks using FFmpeg.
    Returns list of floats 0.0-1.0 (absolute amplitude peaks).
    """
    key = _cache_key(file_path)
    cache_file = _CACHE_DIR / f"{key}.json"

    # Check cache
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            peaks = data.get("peaks", [])
            if peaks:
                logger.debug(f"Waveform cache hit: {Path(file_path).name} ({len(peaks)} peaks)")
                return peaks
        except Exception:
            pass

    # Sample rate for extraction
    # We want PEAKS_PER_SECOND peaks → sample at PEAKS_PER_SECOND * 2 (Nyquist-ish for peaks)
    sample_rate = PEAKS_PER_SECOND * 2  # 400 Hz

    try:
        cmd = [
            ffmpeg_path, "-i", str(file_path),
            "-vn",  # no video
            "-ac", "1",  # mono
            "-ar", str(sample_rate),
            "-f", "s16le",  # raw 16-bit signed little-endian
            "-acodec", "pcm_s16le",
            "-y", "pipe:1"
        ]
        proc = subprocess.run(
            cmd, capture_output=True, timeout=120,
            creationflags=0x08000000  # CREATE_NO_WINDOW on Windows
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            logger.warning(f"Waveform extraction failed: {stderr[:200]}")
            return []

        raw = proc.stdout
        if len(raw) < 4:
            return []

        # Parse 16-bit samples
        n_samples = len(raw) // 2
        samples = struct.unpack(f"<{n_samples}h", raw[:n_samples * 2])

        # Downsample to peaks: take max absolute value per window
        window = max(1, sample_rate // PEAKS_PER_SECOND)  # 2 samples per peak
        peaks = []
        max_val = 32768.0
        for i in range(0, n_samples, window):
            chunk = samples[i:i + window]
            if chunk:
                peak = max(abs(s) for s in chunk) / max_val
                peaks.append(round(min(1.0, peak), 3))

        # Normalize: scale so max peak = 1.0
        max_peak = max(peaks) if peaks else 1.0
        if max_peak > 0.001:
            peaks = [round(min(1.0, p / max_peak), 3) for p in peaks]

        # Save cache
        cache_data = {
            "file": str(file_path),
            "peaks_per_sec": PEAKS_PER_SECOND,
            "num_peaks": len(peaks),
            "peaks": peaks,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")
        logger.info(f"Waveform generated: {Path(file_path).name} ({len(peaks)} peaks, {len(peaks)/PEAKS_PER_SECOND:.1f}s)")
        return peaks

    except subprocess.TimeoutExpired:
        logger.warning(f"Waveform timeout: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Waveform error: {e}")
        return []
