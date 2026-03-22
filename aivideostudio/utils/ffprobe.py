"""FFprobe wrapper — UTF-8 safe."""
import json
import subprocess
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from loguru import logger


@dataclass
class ProbeResult:
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    file_size: int = 0
    has_video: bool = False
    has_audio: bool = False


def probe(file_path: str, ffprobe_path: str = "ffprobe") -> Optional[ProbeResult]:
    """Probe a media file and return info."""
    try:
        cmd = [
            ffprobe_path, "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json", str(file_path)
        ]
        r = subprocess.run(
            cmd, capture_output=True, timeout=30,
            creationflags=0x08000000
        )
        stdout = r.stdout.decode("utf-8", errors="replace")
        if r.returncode != 0:
            stderr = r.stderr.decode("utf-8", errors="replace")
            logger.warning(f"ffprobe failed for {file_path}: {stderr[:200]}")
            return None

        data = json.loads(stdout)
        result = ProbeResult()

        fmt = data.get("format", {})
        result.duration = float(fmt.get("duration", 0))
        result.file_size = int(fmt.get("size", 0))

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video" and not result.has_video:
                result.has_video = True
                result.width = int(stream.get("width", 0))
                result.height = int(stream.get("height", 0))
                result.video_codec = stream.get("codec_name", "")
                # fps
                r_fps = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = r_fps.split("/")
                    result.fps = round(float(num) / float(den), 2)
                except (ValueError, ZeroDivisionError):
                    result.fps = 0.0
            elif codec_type == "audio" and not result.has_audio:
                result.has_audio = True
                result.audio_codec = stream.get("codec_name", "")

        # Image files: no duration
        ext = Path(file_path).suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff",
                    ".tif", ".webp", ".svg"):
            result.duration = 5.0
            result.has_video = True

        logger.info(f"Asset added: {Path(file_path).name} ({result.duration:.1f}s)")
        return result

    except Exception as e:
        logger.error(f"ffprobe error: {e}")
        return None
