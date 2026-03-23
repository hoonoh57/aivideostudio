import subprocess
import json
import sys
from pathlib import Path
from loguru import logger
import pysubs2



def style_to_ass_tags(style: dict) -> str:
    """Convert subtitle_style dict to ASS override tags string."""
    if not style:
        return ""
    parts = []
    if style.get("font"):
        parts.append(r"\fn" + style["font"])
    if style.get("size"):
        parts.append(r"\fs" + str(style["size"]))
    if style.get("bold"):
        parts.append(r"\b1")
    if style.get("italic"):
        parts.append(r"\i1")
    if style.get("underline"):
        parts.append(r"\u1")
    if style.get("font_color"):
        # ASS uses &HBBGGRR& format
        c = style["font_color"].lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            parts.append(r"\c&H" + b + g + r + "&")
    if style.get("outline_color"):
        c = style["outline_color"].lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            parts.append(r"\3c&H" + b + g + r + "&")
    if style.get("outline_size") is not None:
        parts.append(r"\bord" + str(style["outline_size"]))
    if style.get("shadow") is False:
        parts.append(r"\shad0")
    elif style.get("shadow") is True:
        parts.append(r"\shad1")
    if style.get("bg_box"):
        parts.append(r"\4a&H60&")  # semi-transparent bg
    if style.get("alignment"):
        parts.append(r"\an" + str(style["alignment"]))
    # Animation tag (raw ASS)
    anim_tag = style.get("animation_tag", "")
    if anim_tag and anim_tag != "__TYPEWRITER__":
        parts.append(anim_tag.replace("{", "").replace("}", ""))
    if not parts:
        return ""
    return "{" + "".join(parts) + "}"


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
            capture_output=True, timeout=600,
            creationflags=0x08000000
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            logger.error(f"Whisper subprocess failed (rc={result.returncode}): {stderr[-500:]}")
            raise RuntimeError(stderr[-300:])

        logger.info(f"Whisper stdout length: {len(stdout)}, stderr length: {len(stderr)}")
        if stderr:
            logger.debug(f"Whisper stderr: {stderr[:300]}")

        if not stdout.strip():
            logger.warning("Whisper returned empty stdout")
            return []

        segments = json.loads(stdout)
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
        default = subs.styles["Default"]
        default.fontname = fontname
        default.fontsize = fontsize
        default.primarycolor = pysubs2.Color(255, 255, 255)
        default.outlinecolor = pysubs2.Color(0, 0, 0)
        default.outline = outline
        default.shadow = 1
        default.alignment = 2
        for seg in segments:
            text = seg["text"]
            # Apply per-subtitle style overrides as ASS tags
            seg_style = seg.get("style", {})
            if seg_style:
                tags = style_to_ass_tags(seg_style)
                if tags:
                    text = tags + text
            event = pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=text
            )
            subs.append(event)
        subs.save(str(output_path), format_="ass")
        logger.info(f"ASS saved: {output_path}")
        return str(output_path)

    @staticmethod
    def load_subtitle(path):
        subs = pysubs2.load(str(path))
        return [{"start": e.start/1000.0, "end": e.end/1000.0, "text": e.text} for e in subs]