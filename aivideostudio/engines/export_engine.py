import subprocess
import re
from pathlib import Path
from loguru import logger


PRESETS = {
    "YouTube 1080p": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 1920, "height": 1080, "fps": 30,
        "vbitrate": "8M", "abitrate": "192k",
        "extra": ["-preset", "medium", "-crf", "20"]
    },
    "YouTube 1080p (NVENC)": {
        "vcodec": "h264_nvenc", "acodec": "aac",
        "width": 1920, "height": 1080, "fps": 30,
        "vbitrate": "8M", "abitrate": "192k",
        "extra": ["-preset", "p4", "-rc", "vbr", "-cq", "20"]
    },
    "YouTube 4K": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 3840, "height": 2160, "fps": 30,
        "vbitrate": "35M", "abitrate": "320k",
        "extra": ["-preset", "medium", "-crf", "18"]
    },
    "YouTube 4K (NVENC)": {
        "vcodec": "h264_nvenc", "acodec": "aac",
        "width": 3840, "height": 2160, "fps": 30,
        "vbitrate": "35M", "abitrate": "320k",
        "extra": ["-preset", "p4", "-rc", "vbr", "-cq", "18"]
    },
    "YouTube Shorts": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 1080, "height": 1920, "fps": 30,
        "vbitrate": "6M", "abitrate": "192k",
        "extra": ["-preset", "medium", "-crf", "22"]
    },
    "Instagram Reels": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 1080, "height": 1920, "fps": 30,
        "vbitrate": "5M", "abitrate": "128k",
        "extra": ["-preset", "medium", "-crf", "23"]
    },
    "TikTok": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 1080, "height": 1920, "fps": 30,
        "vbitrate": "4M", "abitrate": "128k",
        "extra": ["-preset", "fast", "-crf", "23"]
    },
    "Fast Preview": {
        "vcodec": "libx264", "acodec": "aac",
        "width": 1280, "height": 720, "fps": 30,
        "vbitrate": "2M", "abitrate": "128k",
        "extra": ["-preset", "ultrafast", "-crf", "28"]
    },
    "Fast Preview (NVENC)": {
        "vcodec": "h264_nvenc", "acodec": "aac",
        "width": 1280, "height": 720, "fps": 30,
        "vbitrate": "2M", "abitrate": "128k",
        "extra": ["-preset", "p1", "-rc", "vbr", "-cq", "28"]
    },
}


class ExportEngine:
    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._process = None
        self._cancelled = False

    def export(self, input_path, output_path, preset_name="YouTube 1080p",
               subtitle_path=None, crop_shorts=False,
               on_progress=None, on_complete=None):
        preset = PRESETS.get(preset_name, PRESETS["YouTube 1080p"])
        filters = []

        if crop_shorts or "1920" == str(preset["height"]):
            if preset["width"] < preset["height"]:
                filters.append("crop=ih*9/16:ih")

        filters.append(f"scale={preset['width']}:{preset['height']}:force_original_aspect_ratio=decrease")
        filters.append(f"pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2")
        filters.append(f"fps={preset['fps']}")

        if subtitle_path and Path(subtitle_path).exists():
            sub_path_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
            filters.append(f"subtitles='{sub_path_escaped}'")

        vf = ",".join(filters)

        cmd = [
            self.ffmpeg_path, "-y", "-hide_banner",
            "-progress", "pipe:1",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", preset["vcodec"],
            "-b:v", preset["vbitrate"],
            "-c:a", preset["acodec"],
            "-b:a", preset["abitrate"],
        ]
        cmd.extend(preset.get("extra", []))
        cmd.append(str(output_path))

        logger.info(f"Export: {preset_name} -> {output_path}")
        self._cancelled = False

        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000
            )
        except FileNotFoundError:
            if on_complete:
                on_complete(False, "FFmpeg not found")
            return False

        import threading

        def _read():
            pat = re.compile(r"out_time_ms=(\d+)")
            for line in self._process.stdout:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                m = pat.search(line)
                if m and on_progress:
                    on_progress(int(m.group(1)) / 1_000_000)

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        _, stderr = self._process.communicate()
        t.join(timeout=5)

        ok = self._process.returncode == 0 and not self._cancelled
        if on_complete:
            err_msg = ""
            if not ok and stderr:
                err_msg = stderr.decode("utf-8", errors="replace")[-500:] if isinstance(stderr, bytes) else stderr[-500:]
            on_complete(ok, err_msg)
        logger.info(f"Export {'OK' if ok else 'FAILED'}: {output_path}")
        return ok

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    @staticmethod
    def get_preset_names():
        return list(PRESETS.keys())
