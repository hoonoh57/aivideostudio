import subprocess
from loguru import logger

def detect_cuda():
    try:
        import torch
        ok = torch.cuda.is_available()
        if ok:
            logger.info(f"CUDA: {torch.cuda.get_device_name(0)}")
        return ok
    except ImportError:
        return False

def detect_nvenc(ffmpeg_path):
    if not ffmpeg_path:
        return False
    try:
        r = subprocess.run([ffmpeg_path, "-encoders"],
            capture_output=True, text=True, timeout=10, creationflags=0x08000000)
        return "h264_nvenc" in r.stdout
    except Exception:
        return False

def get_gpu_summary(ffmpeg_path):
    return {"cuda": detect_cuda(), "nvenc": detect_nvenc(ffmpeg_path)}
