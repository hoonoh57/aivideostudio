"""Export Panel — timeline-based export with FFmpeg."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path as _Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QObject
from loguru import logger


class ExportSignals(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


PRESETS = {
    "YouTube 1080p":  {"w": 1920, "h": 1080, "fps": 30, "vb": "8M",  "crf": "20"},
    "YouTube 4K":     {"w": 3840, "h": 2160, "fps": 30, "vb": "35M", "crf": "18"},
    "YouTube Shorts": {"w": 1080, "h": 1920, "fps": 30, "vb": "6M",  "crf": "22"},
    "TikTok":         {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Instagram Reel": {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Twitter/X":      {"w": 1280, "h": 720,  "fps": 30, "vb": "5M",  "crf": "22"},
    "Fast Preview":   {"w": 1280, "h": 720,  "fps": 30, "vb": "2M",  "crf": "28"},
    "Original Size":  {"w": 0,    "h": 0,    "fps": 0,  "vb": "10M", "crf": "20"},
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".svg"}


def parse_time(time_str):
    parts = time_str.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


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
        self._playback_engine = None   # set by MainWindow
        self._get_segments_fn = None   # callback to get timeline segments
        self._sig = ExportSignals()
        self._sig.progress.connect(self._on_progress)
        self._sig.status.connect(self._on_status)
        self._sig.finished.connect(self._on_finished)
        self._sig.error.connect(self._on_error)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Export Video</b>"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        row.addWidget(self.combo_preset)
        lay.addLayout(row)

        self.chk_burn = QCheckBox("Burn subtitles")
        self.chk_burn.setChecked(True)
        lay.addWidget(self.chk_burn)

        self.chk_crop = QCheckBox("Crop for Shorts (9:16)")
        lay.addWidget(self.chk_crop)

        self.chk_gpu = QCheckBox("GPU encoding (NVENC)")
        lay.addWidget(self.chk_gpu)

        self.lbl_input = QLabel("Input: (none)")
        lay.addWidget(self.lbl_input)
        self.lbl_sub = QLabel("Subtitle: (none)")
        lay.addWidget(self.lbl_sub)
        self.lbl_dur = QLabel("")
        lay.addWidget(self.lbl_dur)

        row_btn = QHBoxLayout()
        self.btn_export = QPushButton("Export Timeline")
        self.btn_export.setStyleSheet(
            "QPushButton{background:#2979ff;color:white;padding:10px;font-size:14px;}"
            "QPushButton:hover{background:#448aff;}")
        self.btn_export.clicked.connect(self._on_export)
        row_btn.addWidget(self.btn_export)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(
            "QPushButton{background:#ff5252;color:white;padding:10px;font-size:14px;}")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        row_btn.addWidget(self.btn_cancel)
        lay.addLayout(row_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.lbl_status = QLabel("")
        lay.addWidget(self.lbl_status)
        lay.addStretch()

    # ── external API ────────────────────────────────────────────
    def set_playback_engine(self, engine):
        self._playback_engine = engine

    def set_get_segments(self, fn):
        """Set callback: fn() returns list of segment dicts."""
        self._get_segments_fn = fn

    def set_input(self, path, duration=0.0):
        if path and _Path(path).exists():
            self._video_path = str(path)
            self._video_duration = duration
            self.lbl_input.setText("Input: " + _Path(path).name)
            if duration > 0:
                m, s = divmod(int(duration), 60)
                self.lbl_dur.setText("Duration: " + str(m).zfill(2) + ":" + str(s).zfill(2))
            logger.info("Export input: " + path + " (" + str(round(duration, 1)) + "s)")

    def set_subtitle(self, path):
        if path and _Path(path).exists():
            self._subtitle_path = str(path)
            self.lbl_sub.setText("Subtitle: " + _Path(path).name)

    # ── export logic ────────────────────────────────────────────
    def _on_export(self):
        segments = self._get_timeline_segments()
        if not segments:
            QMessageBox.warning(self, "Export Error",
                                "No clips on timeline.\nAdd clips to timeline first.")
            return

        total_dur = max(s["timeline_end"] for s in segments)
        default = "timeline_export.mp4"
        output, _ = QFileDialog.getSaveFileName(self, "Save Export", default, "Video (*.mp4)")
        if not output:
            return

        preset_name = self.combo_preset.currentText()
        preset = PRESETS[preset_name]
        sub = self._subtitle_path if self.chk_burn.isChecked() else None
        crop = self.chk_crop.isChecked()
        use_gpu = self.chk_gpu.isChecked()

        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Preparing...")

        t = threading.Thread(target=self._run_timeline_export, daemon=True,
                             args=(segments, output, preset, sub, crop, use_gpu, total_dur))
        t.start()

    def _get_timeline_segments(self):
        """Get ordered video segments from playback engine."""
        if self._playback_engine:
            return self._playback_engine.get_ordered_video_segments()
        return []

    def _on_cancel(self):
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def _run_timeline_export(self, segments, output, preset, subtitle, crop, use_gpu, total_dur):
        """Export timeline: trim each segment, then concat."""
        tmpdir = tempfile.mkdtemp(prefix="avs_export_")
        try:
            pw, ph = preset["w"], preset["h"]
            fps = preset["fps"]
            vb = preset["vb"]
            crf = preset.get("crf", "20")

            # Build scale filter
            scale_vf = ""
            if pw > 0 and ph > 0:
                if crop and ph > pw:
                    scale_vf = f"scale=-2:{ph},crop={pw}:{ph}"
                else:
                    scale_vf = (f"scale={pw}:{ph}:force_original_aspect_ratio=decrease,"
                                f"pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2:black")

            # Video codec
            if use_gpu:
                vcodec = ["h264_nvenc", "-preset", "p4", "-rc", "vbr",
                          "-b:v", vb, "-maxrate", vb]
            else:
                vcodec = ["libx264", "-preset", "medium", "-crf", crf, "-b:v", vb]

            # Step 1: Prepare each segment as a normalized clip
            part_files = []
            for i, seg in enumerate(segments):
                self._sig.status.emit(f"Segment {i+1}/{len(segments)}: {_Path(seg['path']).name}")
                self._sig.progress.emit(int(i / len(segments) * 50))

                part_path = os.path.join(tmpdir, f"part_{i:04d}.mp4")
                path = seg["path"]
                is_image = _Path(path).suffix.lower() in IMAGE_EXTS
                dur = seg["timeline_end"] - seg["timeline_start"]

                if is_image:
                    # Image → video
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-loop", "1", "-framerate", str(fps if fps > 0 else 30),
                           "-i", path,
                           "-t", str(dur)]
                    vf_parts = []
                    if scale_vf:
                        vf_parts.append(scale_vf)
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-pix_fmt", "yuv420p", "-an", part_path]
                else:
                    # Video → trim + normalize
                    in_pt = seg.get("in_point", 0)
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-ss", str(in_pt), "-i", path,
                           "-t", str(dur)]
                    vf_parts = []
                    if scale_vf:
                        vf_parts.append(scale_vf)
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-c:a", "aac", "-b:a", "192k",
                            "-pix_fmt", "yuv420p", part_path]

                logger.info(f"Export segment {i}: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                _, stderr_bytes = self._process.communicate()
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                if self._process.returncode != 0:
                    logger.error(f"Segment {i+1} FAILED (rc={self._process.returncode}):\n{stderr[-500:]}")
                    self._sig.error.emit(f"Segment {i+1} failed (rc={self._process.returncode}):\n{stderr[-500:]}")
                    return

                if _Path(part_path).exists():
                    part_files.append(part_path)

            if not part_files:
                self._sig.error.emit("No segments were created.")
                return

            # Step 2: Handle gaps (insert black segments)
            final_parts = []
            for i, seg in enumerate(segments):
                # Gap before this segment?
                if i == 0 and seg["timeline_start"] > 0.1:
                    gap_dur = seg["timeline_start"]
                    gap_path = os.path.join(tmpdir, f"gap_start.mp4")
                    self._make_black(gap_path, gap_dur, pw or 1920, ph or 1080,
                                     fps or 30, vcodec)
                    if _Path(gap_path).exists():
                        final_parts.append(gap_path)
                elif i > 0:
                    prev_end = segments[i-1]["timeline_end"]
                    gap_dur = seg["timeline_start"] - prev_end
                    if gap_dur > 0.05:
                        gap_path = os.path.join(tmpdir, f"gap_{i:04d}.mp4")
                        self._make_black(gap_path, gap_dur, pw or 1920, ph or 1080,
                                         fps or 30, vcodec)
                        if _Path(gap_path).exists():
                            final_parts.append(gap_path)

                final_parts.append(part_files[i])

            # Step 3: Concat
            self._sig.status.emit("Concatenating...")
            self._sig.progress.emit(70)

            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for fp in final_parts:
                    safe = fp.replace("\\", "/")
                    f.write(f"file '{safe}'\n")

            concat_out = output
            if subtitle:
                concat_out = os.path.join(tmpdir, "concat_raw.mp4")

            cmd = [self._ffmpeg, "-y", "-hide_banner",
                   "-f", "concat", "-safe", "0", "-i", concat_list,
                   "-c", "copy", concat_out]
            logger.info(f"Concat: {' '.join(cmd)}")
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000)
            _, stderr_bytes = self._process.communicate()
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            if self._process.returncode != 0:
                logger.error(f"Concat FAILED: {stderr[-500:]}")
                self._sig.error.emit(f"Concat failed:\n{stderr[-500:]}")
                return

            # Step 4: Burn subtitles (optional)
            if subtitle and _Path(subtitle).exists() and concat_out != output:
                self._sig.status.emit("Burning subtitles...")
                self._sig.progress.emit(85)
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
                       "-i", concat_out, "-vf", sub_vf,
                       "-c:v"] + vcodec + [
                       "-c:a", "copy", output]
                logger.info(f"Subtitle burn: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                self._process.communicate()
                if os.path.exists(temp_sub):
                    os.remove(temp_sub)

            self._sig.progress.emit(100)
            if _Path(output).exists():
                mb = _Path(output).stat().st_size / (1024 * 1024)
                self._sig.finished.emit(
                    f"Export complete!\n{_Path(output).name} ({mb:.1f} MB)")
            else:
                self._sig.error.emit("Output file was not created.")

        except Exception as e:
            self._sig.error.emit(str(e))
        finally:
            self._process = None
            # Cleanup temp
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _make_black(self, path, duration, w, h, fps, vcodec):
        """Create a black video segment."""
        cmd = [self._ffmpeg, "-y", "-hide_banner",
               "-f", "lavfi", "-i",
               f"color=c=black:s={w}x{h}:d={duration}:r={fps}",
               "-c:v"] + list(vcodec) + [
               "-pix_fmt", "yuv420p", "-an", path]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=0x08000000)
        p.communicate()

    # ── UI callbacks ────────────────────────────────────────────
    def _on_progress(self, v):
        self.progress.setValue(v)

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setValue(100)
        self.lbl_status.setText(msg.split("\n")[0] if "\n" in msg else msg)
        QMessageBox.information(self, "Export", msg)

    def _on_error(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.lbl_status.setText("Error: " + msg[:100])
        QMessageBox.critical(self, "Export Error", msg)
        logger.error("Export error: " + msg)
