import subprocess
from pathlib import Path
from loguru import logger


class ThumbnailEngine:
    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def generate(self, video_path, output_path=None, time_sec=1.0, width=320):
        if output_path is None:
            p = Path(video_path)
            thumb_dir = p.parent / ".thumbnails"
            thumb_dir.mkdir(exist_ok=True)
            output_path = str(thumb_dir / f"{p.stem}_thumb.jpg")

        if Path(output_path).exists():
            return output_path

        cmd = [
            self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(time_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            str(output_path)
        ]
        try:
            subprocess.run(cmd, timeout=15, creationflags=0x08000000,
                           capture_output=True)
            if Path(output_path).exists():
                logger.info(f"Thumbnail: {output_path}")
                return output_path
        except Exception as e:
            logger.error(f"Thumbnail failed: {e}")
        return None
