from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QTextEdit, QLabel, QFileDialog, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal
from loguru import logger


class TTSWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engine, text, output_path, voice, rate):
        super().__init__()
        self.engine = engine
        self.text = text
        self.output_path = output_path
        self.voice = voice
        self.rate = rate

    def run(self):
        try:
            self.engine.generate(self.text, self.output_path, self.voice, self.rate)
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class TTSPanel(QWidget):
    audio_ready = pyqtSignal(str)

    def __init__(self, tts_engine, parent=None):
        super().__init__(parent)
        self.engine = tts_engine
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("Text to Speech"))

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter text here...")
        self.text_edit.setMaximumHeight(120)
        layout.addWidget(self.text_edit)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Voice:"))
        self.cmb_voice = QComboBox()
        all_voices = {}
        for lang in ["ko", "en", "ja"]:
            all_voices.update(self.engine.get_voices(lang))
        for name, vid in all_voices.items():
            self.cmb_voice.addItem(name, vid)
        row1.addWidget(self.cmb_voice)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Speed:"))
        self.cmb_rate = QComboBox()
        self.cmb_rate.addItems(["-30%", "-20%", "-10%", "+0%", "+10%", "+20%", "+30%"])
        self.cmb_rate.setCurrentText("+0%")
        row2.addWidget(self.cmb_rate)
        layout.addLayout(row2)

        self.btn_generate = QPushButton("Generate Audio")
        self.btn_generate.clicked.connect(self._on_generate)
        layout.addWidget(self.btn_generate)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #aaa;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def _on_generate(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.lbl_status.setText("Please enter text")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", "tts_output.mp3", "Audio Files (*.mp3)")
        if not path:
            return

        voice = self.cmb_voice.currentData()
        rate = self.cmb_rate.currentText()

        self.btn_generate.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Generating...")

        self._worker = TTSWorker(self.engine, text, path, voice, rate)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, path):
        self.progress.hide()
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText(f"Saved: {Path(path).name}")
        self.audio_ready.emit(path)

    def _on_error(self, msg):
        self.progress.hide()
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText(f"Error: {msg}")
