import json
import shutil
import subprocess
from pathlib import Path
from appdirs import user_data_dir
from loguru import logger


class Config:
    APP_NAME = "AIVideoStudio"

    def __init__(self):
        self.data_dir = Path(user_data_dir(self.APP_NAME))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_dir / "settings.json"
        self._settings = self._load_settings()
        self.ffmpeg_path = self._find_binary("ffmpeg", "ffmpeg.exe")
        self.ffprobe_path = self._find_binary("ffprobe", "ffprobe.exe")
        logger.info(f"Config: data_dir={self.data_dir}")
        logger.info(f"FFmpeg: {self.ffmpeg_path}")

    def _find_binary(self, name, exe_name):
        custom = self._settings.get(f"{name}_path")
        if custom and Path(custom).exists():
            return custom
        found = shutil.which(name)
        if found:
            return found
        # 1) Check install root (portable: <root>/ffmpeg/bin/)
        app_root = Path(__file__).resolve().parent.parent
        portable_paths = [
            app_root / "ffmpeg" / "bin",
            app_root.parent / "ffmpeg" / "bin",
        ]
        for base in portable_paths:
            p = base / exe_name
            if p.exists():
                logger.info(f"Found {name} (portable): {p}")
                return str(p)
        # 2) Check common system paths
        for base in ["C:/ffmpeg/bin", "D:/ffmpeg/bin"]:
            p = Path(base) / exe_name
            if p.exists():
                return str(p)
        logger.warning(f"{name} not found")
        return ""

    def verify_ffmpeg(self):
        if not self.ffmpeg_path:
            return False
        try:
            r = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000
            )
            ver = r.stdout.split("\n")[0] if r.stdout else "unknown"
            logger.info(f"FFmpeg verified: {ver}")
            return r.returncode == 0
        except Exception as e:
            logger.error(f"FFmpeg check failed: {e}")
            return False

    def get_hw_accels(self):
        if not self.ffmpeg_path:
            return []
        try:
            r = subprocess.run(
                [self.ffmpeg_path, "-hwaccels"],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000
            )
            lines = r.stdout.strip().split("\n")[1:]
            return [x.strip() for x in lines if x.strip()]
        except Exception:
            return []

    def _load_settings(self):
        if self.settings_path.exists():
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        return {}

    def save_settings(self):
        self.settings_path.write_text(
            json.dumps(self._settings, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value
        self.save_settings()
