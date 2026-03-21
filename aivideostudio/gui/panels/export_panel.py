import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

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
    "YouTube 1080p":  {"w": 1920, "h": 1080, "fps": 30, "vb": "8M"},
    "YouTube Shorts": {"w": 1080, "h": 1920, "fps": 30, "vb": "6M"},
    "TikTok":         {"w": 1080, "h": 1920, "fps": 30, "vb": "5M"},
    "Instagram Reel": {"w": 1080, "h": 1920, "fps": 30, "vb": "5M"},
    "Twitter/X":      {"w": 1280, "h": 720,  "fps": 30, "vb": "5M"},
    "Original Size":  {"w": 0,    "h": 0,    "fps": 0,  "vb": "10M"},
}


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
        self.lbl_input = QLabel("Input: (none)")
        lay.addWidget(self.lbl_input)
        self.lbl_sub = QLabel("Subtitle: (none)")
        lay.addWidget(self.lbl_sub)
        self.lbl_dur = QLabel("")
        lay.addWidget(self.lbl_dur)
        row_btn = QHBoxLayout()
        self.btn_export = QPushButton("Export")
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

    def set_input(self, path, duration=0.0):
        if path and Path(path).exists():
            self._video_path = str(path)
            self._video_duration = duration
            self.lbl_input.setText("Input: " + Path(path).name)
            if duration > 0:
                m, s = divmod(int(duration), 60)
                self.lbl_dur.setText("Duration: " + str(m).zfill(2) + ":" + str(s).zfill(2))
            logger.info("Export input: " + path + " (" + str(round(duration, 1)) + "s)")

    def set_subtitle(self, path):
        if path and Path(path).exists():
            self._subtitle_path = str(path)
            self.lbl_sub.setText("Subtitle: " + Path(path).name)

    def _on_export(self):
        if not self._video_path or not Path(self._video_path).exists():
            QMessageBox.warning(self, "Export Error", "No input video.\nImport a video first.")
            return
        preset_name = self.combo_preset.currentText()
        preset = PRESETS[preset_name]
        stem = Path(self._video_path).stem
        default = stem + "_" + preset_name.replace(" ", "_") + ".mp4"
        output, _ = QFileDialog.getSaveFileName(self, "Save Export", default, "Video (*.mp4)")
        if not output:
            return
        sub = self._subtitle_path if self.chk_burn.isChecked() else None
        crop = self.chk_crop.isChecked()
        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Preparing...")
        t = threading.Thread(target=self._run, daemon=True,
                             args=(self._video_path, output, preset, sub, crop))
        t.start()

    def _on_cancel(self):
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def _run(self, video, output, preset, subtitle, crop):
        try:
            cmd = [self._ffmpeg, "-y", "-hide_banner"]
            vf = []

            # Copy subtitle to temp to avoid path escaping issues
            temp_sub = None
            if subtitle and Path(subtitle).exists():
                temp_sub = os.path.join(tempfile.gettempdir(), "avs_sub" + Path(subtitle).suffix)
                shutil.copy2(subtitle, temp_sub)
                logger.info("Copied subtitle to temp: " + temp_sub)

            cmd += ["-i", video]

            pw, ph = preset["w"], preset["h"]
            if pw > 0 and ph > 0:
                if crop and ph > pw:
                    vf.append("scale=-2:" + str(ph) + ",crop=" + str(pw) + ":" + str(ph))
                else:
                    vf.append(
                        "scale=" + str(pw) + ":" + str(ph) +
                        ":force_original_aspect_ratio=decrease,"
                        "pad=" + str(pw) + ":" + str(ph) + ":(ow-iw)/2:(oh-ih)/2:black")

            if temp_sub:
                safe = temp_sub.replace("\\", "/").replace(":", "\\:")
                if temp_sub.endswith(".ass"):
                    vf.append("ass='" + safe + "'")
                else:
                    vf.append(
                        "subtitles='" + safe + "':"
                        "force_style='FontName=Malgun Gothic,FontSize=24,"
                        "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                        "Outline=2,Shadow=1'")

            if vf:
                cmd += ["-vf", ",".join(vf)]

            cmd += ["-c:v", "libx264", "-preset", "medium",
                    "-b:v", preset["vb"], "-c:a", "aac", "-b:a", "192k"]
            if preset["fps"] > 0:
                cmd += ["-r", str(preset["fps"])]
            cmd.append(output)

            self._sig.status.emit("Encoding...")
            logger.info("Export cmd: " + " ".join(cmd))

            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=0x08000000)

            duration = self._video_duration if self._video_duration > 0 else 1.0
            time_re = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")

            for line in self._process.stderr:
                m = time_re.search(line)
                if m:
                    current = parse_time(m.group(1))
                    pct = min(int(current / duration * 100), 99)
                    self._sig.progress.emit(pct)
                    self._sig.status.emit(
                        "Encoding... " + str(pct) + "% (" +
                        str(round(current, 1)) + "s / " +
                        str(round(duration, 1)) + "s)")

            self._process.wait()

            # Clean up temp subtitle
            if temp_sub and os.path.exists(temp_sub):
                os.remove(temp_sub)

            if self._process.returncode != 0:
                self._sig.error.emit("FFmpeg encoding failed (code " + str(self._process.returncode) + ")")
                return

            if Path(output).exists():
                mb = Path(output).stat().st_size / (1024 * 1024)
                self._sig.progress.emit(100)
                self._sig.finished.emit(
                    "Export complete!\n" + Path(output).name + " (" + str(round(mb, 1)) + " MB)")
            else:
                self._sig.error.emit("Output file was not created.")
        except Exception as e:
            self._sig.error.emit(str(e))
        finally:
            self._process = None

    def _on_progress(self, v):
        self.progress.setValue(v)

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setValue(100)
        self.lbl_status.setText(msg)
        QMessageBox.information(self, "Export", msg)

    def _on_error(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.lbl_status.setText("Error: " + msg[:100])
        QMessageBox.critical(self, "Export Error", msg)
        logger.error("Export error: " + msg)
