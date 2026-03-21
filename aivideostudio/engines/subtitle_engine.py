import subprocess
import json
import sys
from pathlib import Path
from loguru import logger
import pysubs2


class SubtitleEngine:
    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def extract_audio(self, video_path, output_path=None):
        if output_path is None:
            output_path = str(Path(video_path).with_suffix(".wav"))
        cmd = [
            self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path), "-vn",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(output_path)
        ]
        subprocess.run(cmd, creationflags=0x08000000, timeout=120)
        if Path(output_path).exists():
            logger.info(f"Audio extracted: {output_path}")
            return output_path
        return None

    def transcribe(self, audio_path, language="ko", model_size="base"):
        worker_script = Path(__file__).parent / "whisper_worker.py"
        python_exe = sys.executable

        logger.info(f"Transcribing via subprocess: {audio_path}")
        result = subprocess.run(
            [python_exe, str(worker_script), str(audio_path), language, model_size],
            capture_output=True, text=True, timeout=600,
            creationflags=0x08000000
        )

        if result.returncode != 0:
            logger.error(f"Whisper subprocess failed: {result.stderr[-500:]}")
            raise RuntimeError(result.stderr[-300:])

        segments = json.loads(result.stdout)
        logger.info(f"Transcribed {len(segments)} segments")
        return segments

    @staticmethod
    def segments_to_srt(segments, output_path):
        subs = pysubs2.SSAFile()
        for seg in segments:
            event = pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=seg["text"]
            )
            subs.append(event)
        subs.save(str(output_path), format_="srt")
        logger.info(f"SRT saved: {output_path}")
        return str(output_path)

    @staticmethod
    def segments_to_ass(segments, output_path, fontname="Malgun Gothic",
                        fontsize=22, outline=2):
        subs = pysubs2.SSAFile()
        style = subs.styles["Default"]
        style.fontname = fontname
        style.fontsize = fontsize
        style.primarycolor = pysubs2.Color(255, 255, 255)
        style.outlinecolor = pysubs2.Color(0, 0, 0)
        style.outline = outline
        style.shadow = 1
        style.alignment = 2
        for seg in segments:
            event = pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=seg["text"]
            )
            subs.append(event)
        subs.save(str(output_path), format_="ass")
        logger.info(f"ASS saved: {output_path}")
        return str(output_path)

    @staticmethod
    def load_subtitle(path):
        subs = pysubs2.load(str(path))
        return [{"start": e.start/1000.0, "end": e.end/1000.0, "text": e.text} for e in subs]