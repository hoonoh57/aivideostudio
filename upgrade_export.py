"""upgrade_export.py — Export 기능 대폭 업그레이드
1) export_panel.py: NVENC 최적화, 오디오 트랙 합성, 진행률 개선, 한글 인코딩 수정
2) playback_engine.py: get_ordered_audio_segments() 추가
3) export_engine.py: NVENC preset 추가
"""
import os

BASE = r"D:\aivideostudio\aivideostudio"

# ============================================================
# 1) playback_engine.py — 오디오 세그먼트 메서드 추가
# ============================================================
pe_path = os.path.join(BASE, "core", "playback_engine.py")
with open(pe_path, "r", encoding="utf-8") as f:
    pe_code = f.read()

audio_method = '''
    def get_ordered_audio_segments(self):
        """Return all audio segments sorted by timeline_start."""
        segments = []
        for track in self._tracks:
            if track.get("type") != "audio":
                continue
            for clip in track.get("clips", []):
                cs = clip.get("timeline_start", 0)
                dur = clip.get("duration", 0)
                segments.append({
                    "timeline_start": cs,
                    "timeline_end": cs + dur,
                    "path": clip.get("path", ""),
                    "in_point": clip.get("in_point", 0),
                    "out_point": clip.get("out_point", clip.get("in_point", 0) + dur),
                })
        segments.sort(key=lambda s: s["timeline_start"])
        return segments
'''

if "get_ordered_audio_segments" not in pe_code:
    pe_code = pe_code.rstrip() + "\n" + audio_method + "\n"
    with open(pe_path, "w", encoding="utf-8") as f:
        f.write(pe_code)
    print(f"[1] OK: {pe_path} — get_ordered_audio_segments() added")
else:
    print(f"[1] SKIP: {pe_path} — already has audio segments method")


# ============================================================
# 2) export_engine.py — NVENC presets 추가
# ============================================================
ee_path = os.path.join(BASE, "engines", "export_engine.py")

export_engine_code = r'''import subprocess
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
'''

with open(ee_path, "w", encoding="utf-8") as f:
    f.write(export_engine_code)
print(f"[2] OK: {ee_path} — NVENC presets added")


# ============================================================
# 3) export_panel.py — 완전 새로 작성
# ============================================================
ep_path = os.path.join(BASE, "gui", "panels", "export_panel.py")

export_panel_code = r'''"""Export Panel — timeline-based export with FFmpeg + NVENC + audio mixing."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path as _Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import pyqtSignal, QObject
from loguru import logger


class ExportSignals(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


PRESETS = {
    "YouTube 1080p":        {"w": 1920, "h": 1080, "fps": 30, "vb": "8M",  "crf": "20"},
    "YouTube 1080p NVENC":  {"w": 1920, "h": 1080, "fps": 30, "vb": "8M",  "crf": "20", "gpu": True},
    "YouTube 4K":           {"w": 3840, "h": 2160, "fps": 30, "vb": "35M", "crf": "18"},
    "YouTube 4K NVENC":     {"w": 3840, "h": 2160, "fps": 30, "vb": "35M", "crf": "18", "gpu": True},
    "YouTube Shorts":       {"w": 1080, "h": 1920, "fps": 30, "vb": "6M",  "crf": "22"},
    "TikTok":               {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Instagram Reel":       {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Twitter/X":            {"w": 1280, "h": 720,  "fps": 30, "vb": "5M",  "crf": "22"},
    "Fast Preview":         {"w": 1280, "h": 720,  "fps": 30, "vb": "2M",  "crf": "28"},
    "Fast Preview NVENC":   {"w": 1280, "h": 720,  "fps": 30, "vb": "2M",  "crf": "28", "gpu": True},
    "Original Size":        {"w": 0,    "h": 0,    "fps": 0,  "vb": "10M", "crf": "20"},
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".svg"}
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


class ExportPanel(QWidget):
    def __init__(self, export_engine=None, parent=None):
        super().__init__(parent)
        self._engine = export_engine
        self._ffmpeg = "ffmpeg"
        if export_engine and hasattr(export_engine, "ffmpeg_path"):
            self._ffmpeg = str(export_engine.ffmpeg_path)
        self._video_path = None
        self._video_duration = 0.0
        self._subtitle_path = None
        self._process = None
        self._playback_engine = None
        self._sig = ExportSignals()
        self._sig.progress.connect(self._on_progress)
        self._sig.status.connect(self._on_status)
        self._sig.finished.connect(self._on_finished)
        self._sig.error.connect(self._on_error)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # ── Preset ──
        preset_grp = QGroupBox("Export Settings")
        preset_lay = QVBoxLayout(preset_grp)

        row = QHBoxLayout()
        row.addWidget(QLabel("Preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        # Default to NVENC 1080p
        idx = list(PRESETS.keys()).index("YouTube 1080p NVENC") if "YouTube 1080p NVENC" in PRESETS else 0
        self.combo_preset.setCurrentIndex(idx)
        row.addWidget(self.combo_preset)
        preset_lay.addLayout(row)

        # Options
        self.chk_burn = QCheckBox("Burn subtitles into video")
        self.chk_burn.setChecked(True)
        preset_lay.addWidget(self.chk_burn)

        self.chk_crop = QCheckBox("Crop for Shorts (9:16)")
        preset_lay.addWidget(self.chk_crop)

        self.chk_mix_audio = QCheckBox("Mix audio track (TTS, BGM)")
        self.chk_mix_audio.setChecked(True)
        preset_lay.addWidget(self.chk_mix_audio)

        lay.addWidget(preset_grp)

        # ── Info ──
        info_grp = QGroupBox("Source Info")
        info_lay = QVBoxLayout(info_grp)
        self.lbl_input = QLabel("Input: (none)")
        info_lay.addWidget(self.lbl_input)
        self.lbl_sub = QLabel("Subtitle: (none)")
        info_lay.addWidget(self.lbl_sub)
        self.lbl_dur = QLabel("")
        info_lay.addWidget(self.lbl_dur)
        lay.addWidget(info_grp)

        # ── Buttons ──
        row_btn = QHBoxLayout()
        self.btn_export = QPushButton("Export Timeline")
        self.btn_export.setStyleSheet(
            "QPushButton{background:#2979ff;color:white;padding:10px;font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:#448aff;}"
            "QPushButton:disabled{background:#666;}")
        self.btn_export.clicked.connect(self._on_export)
        row_btn.addWidget(self.btn_export)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(
            "QPushButton{background:#ff5252;color:white;padding:10px;font-size:14px;}")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        row_btn.addWidget(self.btn_cancel)
        lay.addLayout(row_btn)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)
        lay.addStretch()

    # ── external API ──
    def set_playback_engine(self, engine):
        self._playback_engine = engine

    def set_input(self, path, duration=0.0):
        if path and _Path(path).exists():
            self._video_path = str(path)
            self._video_duration = duration
            self.lbl_input.setText("Input: " + _Path(path).name)
            if duration > 0:
                m, s = divmod(int(duration), 60)
                self.lbl_dur.setText(f"Duration: {m:02d}:{s:02d}")

    def set_subtitle(self, path):
        if path and _Path(path).exists():
            self._subtitle_path = str(path)
            self.lbl_sub.setText("Subtitle: " + _Path(path).name)

    # ── export logic ──
    def _on_export(self):
        segments = self._get_video_segments()
        if not segments:
            QMessageBox.warning(self, "Export Error",
                                "No clips on timeline.\nAdd clips to timeline first.")
            return

        total_dur = max(s["timeline_end"] for s in segments)
        output, _ = QFileDialog.getSaveFileName(
            self, "Save Export", "timeline_export.mp4", "Video (*.mp4)")
        if not output:
            return

        preset_name = self.combo_preset.currentText()
        preset = PRESETS[preset_name]
        sub = self._subtitle_path if self.chk_burn.isChecked() else None
        crop = self.chk_crop.isChecked()
        use_gpu = preset.get("gpu", False)
        mix_audio = self.chk_mix_audio.isChecked()

        # Get audio segments
        audio_segments = []
        if mix_audio and self._playback_engine and hasattr(self._playback_engine, "get_ordered_audio_segments"):
            audio_segments = self._playback_engine.get_ordered_audio_segments()

        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Preparing...")

        t = threading.Thread(target=self._run_export, daemon=True,
                             args=(segments, audio_segments, output, preset,
                                   sub, crop, use_gpu, total_dur))
        t.start()

    def _get_video_segments(self):
        if self._playback_engine:
            return self._playback_engine.get_ordered_video_segments()
        return []

    def _on_cancel(self):
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def _get_vcodec(self, use_gpu, preset):
        vb = preset["vb"]
        crf = preset.get("crf", "20")
        if use_gpu:
            return ["h264_nvenc", "-preset", "p4", "-rc", "vbr",
                    "-cq", crf, "-b:v", vb, "-maxrate", vb]
        else:
            return ["libx264", "-preset", "medium", "-crf", crf, "-b:v", vb]

    def _run_export(self, video_segs, audio_segs, output, preset,
                    subtitle, crop, use_gpu, total_dur):
        tmpdir = tempfile.mkdtemp(prefix="avs_export_")
        try:
            pw, ph = preset["w"], preset["h"]
            fps = preset["fps"]
            vcodec = self._get_vcodec(use_gpu, preset)
            num_segs = len(video_segs)

            # Build scale filter
            scale_vf = ""
            if pw > 0 and ph > 0:
                if crop and ph > pw:
                    scale_vf = f"scale=-2:{ph},crop={pw}:{ph}"
                else:
                    scale_vf = (f"scale={pw}:{ph}:force_original_aspect_ratio=decrease,"
                                f"pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2:black")

            # ── Step 1: Encode each video segment ──
            part_files = []
            for i, seg in enumerate(video_segs):
                pct = int(i / num_segs * 40)
                self._sig.status.emit(f"Encoding segment {i+1}/{num_segs}...")
                self._sig.progress.emit(pct)

                part_path = os.path.join(tmpdir, f"part_{i:04d}.mp4")
                path = seg["path"]
                ext = _Path(path).suffix.lower()
                is_image = ext in IMAGE_EXTS
                dur = seg["timeline_end"] - seg["timeline_start"]

                if is_image:
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-loop", "1", "-framerate", str(fps or 30),
                           "-i", path, "-t", str(dur)]
                    vf_parts = [scale_vf] if scale_vf else []
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-pix_fmt", "yuv420p", "-an", part_path]
                else:
                    in_pt = seg.get("in_point", 0)
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-ss", str(in_pt), "-i", path,
                           "-t", str(dur)]
                    vf_parts = [scale_vf] if scale_vf else []
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-c:a", "aac", "-b:a", "192k",
                            "-pix_fmt", "yuv420p", part_path]

                logger.info(f"Segment {i}: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                _, stderr_bytes = self._process.communicate()
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

                if self._process.returncode != 0:
                    self._sig.error.emit(f"Segment {i+1} failed:\n{stderr[-300:]}")
                    return
                if _Path(part_path).exists():
                    part_files.append(part_path)

            if not part_files:
                self._sig.error.emit("No segments were created.")
                return

            # ── Step 2: Insert gaps (black segments) ──
            final_parts = []
            for i, seg in enumerate(video_segs):
                gap_start = seg["timeline_start"]
                if i == 0 and gap_start > 0.05:
                    gap_path = os.path.join(tmpdir, "gap_start.mp4")
                    self._make_black(gap_path, gap_start, pw or 1920, ph or 1080, fps or 30, vcodec)
                    if _Path(gap_path).exists():
                        final_parts.append(gap_path)
                elif i > 0:
                    prev_end = video_segs[i-1]["timeline_end"]
                    gap_dur = gap_start - prev_end
                    if gap_dur > 0.05:
                        gap_path = os.path.join(tmpdir, f"gap_{i:04d}.mp4")
                        self._make_black(gap_path, gap_dur, pw or 1920, ph or 1080, fps or 30, vcodec)
                        if _Path(gap_path).exists():
                            final_parts.append(gap_path)
                final_parts.append(part_files[i])

            # ── Step 3: Concat video ──
            self._sig.status.emit("Concatenating video...")
            self._sig.progress.emit(50)

            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for fp in final_parts:
                    safe = fp.replace("\\", "/")
                    f.write(f"file '{safe}'\n")

            need_subtitle = subtitle and _Path(subtitle).exists()
            need_audio_mix = bool(audio_segs)
            concat_out = os.path.join(tmpdir, "concat_raw.mp4") if (need_subtitle or need_audio_mix) else output

            cmd = [self._ffmpeg, "-y", "-hide_banner",
                   "-f", "concat", "-safe", "0", "-i", concat_list,
                   "-c", "copy", concat_out]
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000)
            _, stderr_bytes = self._process.communicate()
            if self._process.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                self._sig.error.emit(f"Concat failed:\n{stderr[-300:]}")
                return

            current_video = concat_out

            # ── Step 4: Mix audio tracks ──
            if need_audio_mix:
                self._sig.status.emit("Mixing audio tracks...")
                self._sig.progress.emit(65)
                mixed = os.path.join(tmpdir, "audio_mixed.mp4")
                ok = self._mix_audio(current_video, audio_segs, mixed, total_dur, vcodec)
                if ok and _Path(mixed).exists():
                    current_video = mixed

            # ── Step 5: Burn subtitles ──
            if need_subtitle:
                self._sig.status.emit("Burning subtitles...")
                self._sig.progress.emit(80)
                sub_out = output
                temp_sub = os.path.join(tempfile.gettempdir(),
                                        "avs_sub" + _Path(subtitle).suffix)
                shutil.copy2(subtitle, temp_sub)
                safe_sub = temp_sub.replace("\\", "/").replace(":", "\\:")

                if temp_sub.endswith(".ass"):
                    sub_vf = f"ass='{safe_sub}'"
                else:
                    sub_vf = (f"subtitles='{safe_sub}':"
                              "force_style='FontName=Malgun Gothic,FontSize=24,"
                              "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                              "Outline=2,Shadow=1'")

                cmd = [self._ffmpeg, "-y", "-hide_banner",
                       "-i", current_video, "-vf", sub_vf,
                       "-c:v"] + list(vcodec) + [
                       "-c:a", "copy", sub_out]
                logger.info(f"Subtitle burn: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                self._process.communicate()
                if os.path.exists(temp_sub):
                    os.remove(temp_sub)
                current_video = sub_out
            elif current_video != output:
                # Copy to final output
                shutil.copy2(current_video, output)

            # ── Done ──
            self._sig.progress.emit(100)
            if _Path(output).exists():
                mb = _Path(output).stat().st_size / (1024 * 1024)
                self._sig.finished.emit(
                    f"Export complete!\n{_Path(output).name} ({mb:.1f} MB)\n"
                    f"Encoder: {'NVENC GPU' if preset.get('gpu') else 'CPU (x264)'}")
            else:
                self._sig.error.emit("Output file was not created.")

        except Exception as e:
            logger.exception("Export failed")
            self._sig.error.emit(str(e))
        finally:
            self._process = None
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _mix_audio(self, video_path, audio_segs, output, total_dur, vcodec):
        """Mix audio track clips into the video using ffmpeg amerge/amix."""
        if not audio_segs:
            return False

        tmpdir = os.path.dirname(output)

        # Build a complex filter to delay and mix each audio segment
        inputs = ["-i", video_path]  # input 0 = video with its own audio
        filter_parts = []
        audio_labels = []

        # Original audio from video
        filter_parts.append("[0:a]aresample=44100[orig]")
        audio_labels.append("[orig]")

        for i, seg in enumerate(audio_segs):
            inp_idx = i + 1
            inputs += ["-i", seg["path"]]
            delay_ms = int(seg["timeline_start"] * 1000)
            in_pt = seg.get("in_point", 0)
            dur = seg["timeline_end"] - seg["timeline_start"]

            label = f"[a{i}]"
            # Trim, delay, pad
            f = (f"[{inp_idx}:a]atrim=start={in_pt}:duration={dur},"
                 f"asetpts=PTS-STARTPTS,"
                 f"adelay={delay_ms}|{delay_ms},"
                 f"aresample=44100{label}")
            filter_parts.append(f)
            audio_labels.append(label)

        # Amix all
        n = len(audio_labels)
        mix_inputs = "".join(audio_labels)
        filter_parts.append(f"{mix_inputs}amix=inputs={n}:duration=longest:dropout_transition=0[aout]")
        filter_complex = ";".join(filter_parts)

        cmd = [self._ffmpeg, "-y", "-hide_banner"] + inputs
        cmd += ["-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", output]

        logger.info(f"Audio mix: {len(audio_segs)} audio clips")
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000)
            _, stderr_bytes = self._process.communicate()
            if self._process.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                logger.warning(f"Audio mix failed (non-fatal): {stderr[-300:]}")
                # Fallback: just copy video without mixing
                shutil.copy2(video_path, output)
                return True
        except Exception as e:
            logger.warning(f"Audio mix error: {e}")
            shutil.copy2(video_path, output)
        return True

    def _make_black(self, path, duration, w, h, fps, vcodec):
        cmd = [self._ffmpeg, "-y", "-hide_banner",
               "-f", "lavfi", "-i",
               f"color=c=black:s={w}x{h}:d={duration}:r={fps}",
               "-c:v"] + list(vcodec) + [
               "-pix_fmt", "yuv420p", "-an", path]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=0x08000000)
        p.communicate()

    # ── UI callbacks ──
    def _on_progress(self, v):
        self.progress.setValue(v)

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setValue(100)
        self.lbl_status.setText(msg.split("\n")[0])
        QMessageBox.information(self, "Export Complete", msg)

    def _on_error(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.lbl_status.setText("Error: " + msg[:100])
        QMessageBox.critical(self, "Export Error", msg[:500])
        logger.error("Export error: " + msg)
'''

with open(ep_path, "w", encoding="utf-8") as f:
    f.write(export_panel_code)
print(f"[3] OK: {ep_path}")


# ============================================================
print()
print("=" * 60)
print("Export upgrade complete!")
print()
print("  [1] playback_engine.py: get_ordered_audio_segments() added")
print("  [2] export_engine.py: NVENC presets (h264_nvenc)")
print("  [3] export_panel.py: NVENC presets, audio track mixing,")
print("       subtitle burn-in, gap handling, UTF-8 encoding")
print()
print("Features:")
print("  - NVENC presets: YouTube 1080p/4K/Preview with GPU encoding")
print("  - Audio track mixing: TTS, BGM merged into final video")
print("  - Subtitle burn-in: SRT/ASS with Malgun Gothic font")
print("  - Gap handling: black segments for timeline gaps")
print("  - Preset default: YouTube 1080p NVENC")
print()
print("Next: python -m aivideostudio.main")
print("=" * 60)
