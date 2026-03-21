import re
import subprocess
import threading
from loguru import logger

class FFmpegEngine:
    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._process = None
        self._cancelled = False

    def run(self, args, total_duration=0.0, on_progress=None, on_complete=None):
        cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-progress", "pipe:1"] + args
        logger.info(f"FFmpeg cmd: {len(cmd)} args")
        self._cancelled = False
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=0x08000000)
        except FileNotFoundError:
            if on_complete:
                on_complete(False, "FFmpeg not found")
            return False

        def _read():
            pat = re.compile(r"out_time_ms=(\d+)")
            while self._process and self._process.poll() is None:
                line = self._process.stdout.readline()
                if not line:
                    break
                m = pat.search(line)
                if m and total_duration > 0 and on_progress:
                    cur = int(m.group(1)) / 1_000_000
                    on_progress(min(100.0, cur / total_duration * 100))

        th = threading.Thread(target=_read, daemon=True)
        th.start()
        _, stderr = self._process.communicate()
        th.join(timeout=5)
        ok = self._process.returncode == 0 and not self._cancelled
        if on_progress:
            on_progress(100.0 if ok else 0.0)
        if on_complete:
            on_complete(ok, "" if ok else (stderr or "")[-500:])
        return ok

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
