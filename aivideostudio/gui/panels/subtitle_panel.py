import os
import json
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSpinBox, QColorDialog, QFontComboBox,
    QAbstractItemView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from loguru import logger

import pysubs2


class WhisperWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, engine, video_path, language, model_size):
        super().__init__()
        self.engine = engine
        self.video_path = video_path
        self.language = language
        self.model_size = model_size

    def run(self):
        try:
            from pathlib import Path
            ext = Path(self.video_path).suffix.lower()
            audio_exts = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}

            if ext in audio_exts:
                # Audio file: skip extraction, use directly
                self.progress.emit("Transcribing audio (GPU)... please wait")
                audio = self.video_path
            else:
                # Video file: extract audio first
                self.progress.emit("Extracting audio...")
                audio = self.engine.extract_audio(self.video_path)
                if not audio:
                    self.error.emit("Audio extraction failed")
                    return
                self.progress.emit("Transcribing (GPU)... please wait")

            segments = self.engine.transcribe(audio, self.language, self.model_size)
            self.finished.emit(segments)
        except Exception as e:
            self.error.emit(str(e))


class SubtitlePanel(QWidget):
    subtitle_ready = pyqtSignal(str)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._video_path = None
        self._segments = []
        self._worker = None
        self._last_save_path = None
        self._font_name = "Malgun Gothic"
        self._font_size = 22
        self._font_color = QColor(255, 255, 255)
        self._outline_color = QColor(0, 0, 0)
        self._outline_size = 2
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        row_gen = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Subtitle")
        self.btn_generate.setStyleSheet(
            "QPushButton{background:#00c853;color:white;padding:8px;font-weight:bold;}"
            "QPushButton:hover{background:#00e676;}")
        self.btn_generate.clicked.connect(self._on_generate)
        row_gen.addWidget(self.btn_generate)
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["ko", "en", "ja", "zh", "auto"])
        row_gen.addWidget(self.combo_lang)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["base", "small", "medium", "large"])
        self.combo_model.setCurrentIndex(2)  # default: medium
        row_gen.addWidget(self.combo_model)
        lay.addLayout(row_gen)

        self.lbl_status = QLabel("")
        lay.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Start", "End", "Text"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        lay.addWidget(self.table)

        row_edit = QHBoxLayout()
        btn_add = QPushButton("+ Add Row")
        btn_add.clicked.connect(self._add_row)
        row_edit.addWidget(btn_add)
        btn_del = QPushButton("- Delete Row")
        btn_del.clicked.connect(self._delete_row)
        row_edit.addWidget(btn_del)
        lay.addLayout(row_edit)

        style_grp = QGroupBox("Subtitle Style")
        style_lay = QVBoxLayout(style_grp)
        row_font = QHBoxLayout()
        row_font.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self._font_name))
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        row_font.addWidget(self.font_combo)
        row_font.addWidget(QLabel("Size:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(8, 120)
        self.spin_size.setValue(self._font_size)
        self.spin_size.valueChanged.connect(self._on_size_changed)
        row_font.addWidget(self.spin_size)
        style_lay.addLayout(row_font)

        row_color = QHBoxLayout()
        self.btn_font_color = QPushButton("Font Color")
        self.btn_font_color.setStyleSheet("background:#ffffff;color:#000000;padding:5px;")
        self.btn_font_color.clicked.connect(self._pick_font_color)
        row_color.addWidget(self.btn_font_color)
        self.btn_outline_color = QPushButton("Outline Color")
        self.btn_outline_color.setStyleSheet("background:#000000;color:#ffffff;padding:5px;")
        self.btn_outline_color.clicked.connect(self._pick_outline_color)
        row_color.addWidget(self.btn_outline_color)
        row_color.addWidget(QLabel("Outline:"))
        self.spin_outline = QSpinBox()
        self.spin_outline.setRange(0, 10)
        self.spin_outline.setValue(self._outline_size)
        self.spin_outline.valueChanged.connect(self._on_outline_changed)
        row_color.addWidget(self.spin_outline)
        style_lay.addLayout(row_color)

        self.lbl_preview = QLabel("Preview Text")
        self._update_preview_style()
        style_lay.addWidget(self.lbl_preview)
        lay.addWidget(style_grp)

        row_save = QHBoxLayout()
        btn_srt = QPushButton("Save SRT")
        btn_srt.setStyleSheet("QPushButton{background:#1565c0;color:white;padding:8px;}"
                              "QPushButton:hover{background:#1976d2;}")
        btn_srt.clicked.connect(lambda: self._save_with_dialog("srt"))
        row_save.addWidget(btn_srt)
        btn_ass = QPushButton("Save ASS")
        btn_ass.setStyleSheet("QPushButton{background:#1565c0;color:white;padding:8px;}"
                              "QPushButton:hover{background:#1976d2;}")
        btn_ass.clicked.connect(lambda: self._save_with_dialog("ass"))
        row_save.addWidget(btn_ass)
        lay.addLayout(row_save)

    def set_video_path(self, path):
        self._video_path = path

    def _on_font_changed(self, font):
        self._font_name = font.family()
        self._update_preview_style()

    def _on_size_changed(self, value):
        self._font_size = value
        self._update_preview_style()

    def _on_outline_changed(self, value):
        self._outline_size = value

    def _update_preview_style(self):
        fc = self._font_color.name()
        oc = self._outline_color.name()
        self.lbl_preview.setStyleSheet(
            "QLabel{"
            "  font-family:'" + self._font_name + "';"
            "  font-size:" + str(self._font_size) + "px;"
            "  color:" + fc + ";"
            "  background:#333;"
            "  padding:8px;"
            "  border:2px solid " + oc + ";"
            "}")
        if self._segments:
            self.lbl_preview.setText(self._segments[0]["text"])
        else:
            self.lbl_preview.setText("Preview Text")

    def _on_generate(self):
        if not self._video_path:
            self.lbl_status.setText("No video loaded")
            return
        self.btn_generate.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_status.setText("Starting...")
        self._worker = WhisperWorker(
            self.engine, self._video_path,
            self.combo_lang.currentText(),
            self.combo_model.currentText())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, segments):
        self._segments = segments
        self.progress.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("Done: " + str(len(segments)) + " segments")
        self._fill_table()
        self._update_preview_style()
        self._auto_save()

    def _on_error(self, msg):
        self.progress.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("Error: " + msg[:80])
        logger.error("Whisper error: " + msg)

    def _fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._segments))
        for i, seg in enumerate(self._segments):
            self.table.setItem(i, 0, QTableWidgetItem(str(round(seg["start"], 1))))
            self.table.setItem(i, 1, QTableWidgetItem(str(round(seg["end"], 1))))
            self.table.setItem(i, 2, QTableWidgetItem(seg["text"]))
        self.table.blockSignals(False)

    def _on_cell_changed(self, row, col):
        if row >= len(self._segments):
            return
        item = self.table.item(row, col)
        if not item:
            return
        text = item.text().strip()
        try:
            if col == 0:
                self._segments[row]["start"] = float(text)
            elif col == 1:
                self._segments[row]["end"] = float(text)
            elif col == 2:
                self._segments[row]["text"] = text
        except ValueError:
            pass

    def _add_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self._segments):
            ref = self._segments[current_row]
            new_start = ref["end"]
            if current_row + 1 < len(self._segments):
                new_end = self._segments[current_row + 1]["start"]
                if new_end <= new_start:
                    new_end = new_start + 2.0
            else:
                new_end = new_start + 2.0
            insert_at = current_row + 1
        else:
            if self._segments:
                new_start = self._segments[-1]["end"]
            else:
                new_start = 0.0
            new_end = new_start + 2.0
            insert_at = len(self._segments)
        new_seg = {"start": round(new_start, 1), "end": round(new_end, 1), "text": "New subtitle"}
        self._segments.insert(insert_at, new_seg)
        self._fill_table()
        self.table.selectRow(insert_at)

    def _delete_row(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._segments):
            self._segments.pop(row)
            self._fill_table()
            if self._segments:
                select = min(row, len(self._segments) - 1)
                self.table.selectRow(select)

    def _pick_font_color(self):
        c = QColorDialog.getColor(self._font_color, self, "Font Color")
        if c.isValid():
            self._font_color = c
            fg = "#000" if c.lightness() > 128 else "#fff"
            self.btn_font_color.setStyleSheet(
                "background:" + c.name() + ";color:" + fg + ";padding:5px;")
            self._update_preview_style()

    def _pick_outline_color(self):
        c = QColorDialog.getColor(self._outline_color, self, "Outline Color")
        if c.isValid():
            self._outline_color = c
            fg = "#000" if c.lightness() > 128 else "#fff"
            self.btn_outline_color.setStyleSheet(
                "background:" + c.name() + ";color:" + fg + ";padding:5px;")
            self._update_preview_style()

    def _save_with_dialog(self, fmt):
        if not self._segments:
            QMessageBox.warning(self, "Save", "No subtitles to save.")
            return
        if self._video_path:
            default_name = Path(self._video_path).stem + "_subtitle." + fmt
            default_dir = str(Path(self._video_path).parent)
        else:
            default_name = "subtitle." + fmt
            default_dir = ""
        if self._last_save_path:
            default_dir = str(Path(self._last_save_path).parent)
            default_name = Path(self._last_save_path).stem + "." + fmt
        if fmt == "srt":
            filter_str = "SRT Subtitle (*.srt)"
        else:
            filter_str = "ASS Subtitle (*.ass)"
        full_default = str(Path(default_dir) / default_name)
        path, _ = QFileDialog.getSaveFileName(self, "Save " + fmt.upper() + " Subtitle", full_default, filter_str)
        if not path:
            return
        self._last_save_path = path
        if fmt == "srt":
            self._save_srt(path)
        else:
            self._save_ass(path)
        self.lbl_status.setText("Saved: " + path)
        self.subtitle_ready.emit(path)

    def _save_srt(self, path):
        subs = pysubs2.SSAFile()
        for seg in self._segments:
            subs.append(pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=seg["text"]))
        subs.save(str(path), format_="srt")
        logger.info("SRT saved: " + path)

    def _save_ass(self, path):
        subs = pysubs2.SSAFile()
        style = subs.styles["Default"]
        style.fontname = self._font_name
        style.fontsize = self._font_size
        fc = self._font_color
        style.primarycolor = pysubs2.Color(fc.red(), fc.green(), fc.blue())
        oc = self._outline_color
        style.outlinecolor = pysubs2.Color(oc.red(), oc.green(), oc.blue())
        style.outline = self._outline_size
        style.shadow = 1
        style.alignment = 2
        for seg in self._segments:
            subs.append(pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=seg["text"]))
        subs.save(str(path), format_="ass")
        logger.info("ASS saved: " + path + " (font=" + self._font_name + ", size=" + str(self._font_size) + ")")

    def _auto_save(self):
        if self._segments and self._video_path:
            base = Path(self._video_path).parent / (Path(self._video_path).stem + "_subtitle.srt")
            self._save_srt(str(base))
            self._last_save_path = str(base)
            self.lbl_status.setText("Saved: " + str(base))
            self.subtitle_ready.emit(str(base))
