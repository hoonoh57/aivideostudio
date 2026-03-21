import json
import subprocess
from dataclasses import dataclass
from loguru import logger

@dataclass
class MediaInfo:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    file_size: int
    has_audio: bool
    has_video: bool

def probe(file_path, ffprobe_path="ffprobe"):
    cmd = [ffprobe_path, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(file_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=30, creationflags=0x08000000)
        data = json.loads(r.stdout)
    except Exception as e:
        logger.error(f"ffprobe failed: {e}")
        return None

    fmt = data.get("format", {})
    streams = data.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    aus = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = 0.0
    if vs:
        parts = vs.get("r_frame_rate", "0/1").split("/")
        fps = int(parts[0]) / int(parts[1]) if int(parts[1]) else 0.0

    return MediaInfo(
        path=str(file_path), duration=float(fmt.get("duration", 0)),
        width=int(vs.get("width", 0)) if vs else 0,
        height=int(vs.get("height", 0)) if vs else 0,
        fps=round(fps, 3),
        video_codec=vs.get("codec_name", "") if vs else "",
        audio_codec=aus.get("codec_name", "") if aus else "",
        file_size=int(fmt.get("size", 0)),
        has_audio=aus is not None, has_video=vs is not None)
