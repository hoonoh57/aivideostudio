"""upgrade_tts.py — TTS를 Edge-TTS + GPT-SoVITS 듀얼 엔진으로 완전 업그레이드"""
import os

BASE = r"D:\aivideostudio\aivideostudio"

# ============================================================
# 1) tts_engine.py — 완전 새로 작성
# ============================================================
tts_engine_code = r'''import asyncio
import json
import os
import struct
import tempfile
from pathlib import Path
from io import BytesIO
from loguru import logger

import requests


# ─── Edge-TTS voices ───
KO_VOICES = {
    "SunHi (Female)": "ko-KR-SunHiNeural",
    "InJoon (Male)": "ko-KR-InJoonNeural",
    "HyunSu (Male)": "ko-KR-HyunsuNeural",
}
EN_VOICES = {
    "Jenny (Female)": "en-US-JennyNeural",
    "Guy (Male)": "en-US-GuyNeural",
}
JA_VOICES = {
    "Nanami (Female)": "ja-JP-NanamiNeural",
    "Keita (Male)": "ja-JP-KeitaNeural",
}


class EdgeTTSEngine:
    """Microsoft Edge TTS (free, cloud-based)."""
    name = "Edge-TTS"

    def __init__(self):
        self.default_voice = "ko-KR-SunHiNeural"
        self.default_rate = "+0%"

    async def _generate(self, text, output_path, voice=None, rate=None, **kw):
        import edge_tts
        voice = voice or self.default_voice
        rate = rate or self.default_rate
        comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await comm.save(str(output_path))
        logger.info(f"[Edge-TTS] saved: {output_path}")

    def generate(self, text, output_path, voice=None, rate=None, **kw):
        asyncio.run(self._generate(text, output_path, voice, rate))
        return str(output_path)

    def get_voices(self, lang="ko"):
        if lang == "ko":
            return KO_VOICES
        elif lang == "en":
            return EN_VOICES
        elif lang == "ja":
            return JA_VOICES
        return {**KO_VOICES, **EN_VOICES, **JA_VOICES}

    def is_available(self):
        try:
            import edge_tts
            return True
        except ImportError:
            return False


class SoVITSEngine:
    """GPT-SoVITS API client (local HTTP server)."""
    name = "GPT-SoVITS"

    def __init__(self, api_url="http://127.0.0.1:9880",
                 ref_audio="D:/GPT-SoVITS/ref_audio.wav",
                 ref_text="",
                 ref_lang="ko"):
        self.api_url = api_url.rstrip("/")
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.ref_lang = ref_lang

    def generate(self, text, output_path, voice=None, rate=None,
                 text_lang="ko", ref_audio=None, ref_text=None,
                 ref_lang=None, speed=1.0, **kw):
        ref_audio = ref_audio or self.ref_audio
        ref_text = ref_text or self.ref_text
        ref_lang = ref_lang or self.ref_lang

        payload = {
            "text": text,
            "text_lang": text_lang,
            "ref_audio_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_lang": ref_lang,
            "text_split_method": "cut5",
            "batch_size": 1,
            "speed_factor": speed,
            "media_type": "wav",
            "streaming_mode": False,
            "parallel_infer": True,
            "repetition_penalty": 1.35,
            "sample_steps": 32,
            "super_sampling": False,
        }

        logger.info(f"[SoVITS] POST {self.api_url}/tts text={text[:30]}...")
        try:
            resp = requests.post(f"{self.api_url}/tts", json=payload, timeout=120)
        except requests.ConnectionError:
            raise ConnectionError(
                "GPT-SoVITS server not running! Start it first:\n"
                "  cd /d D:\\GPT-SoVITS\n"
                "  .\\runtime\\python api_v2.py -a 127.0.0.1 -p 9880"
            )

        if resp.status_code != 200:
            error_msg = resp.text[:300]
            logger.error(f"[SoVITS] API error {resp.status_code}: {error_msg}")
            raise RuntimeError(f"GPT-SoVITS error {resp.status_code}: {error_msg}")

        # Save WAV
        out = str(output_path)
        if not out.lower().endswith(".wav"):
            out = str(Path(output_path).with_suffix(".wav"))

        with open(out, "wb") as f:
            f.write(resp.content)

        logger.info(f"[SoVITS] saved: {out} ({len(resp.content)} bytes)")
        return out

    def get_voices(self, lang="ko"):
        return {"GPT-SoVITS (Clone)": "sovits_clone"}

    def is_available(self):
        try:
            resp = requests.get(f"{self.api_url}/tts", timeout=3)
            return True
        except Exception:
            return False

    def set_ref_audio(self, path, text="", lang="ko"):
        self.ref_audio = path
        self.ref_text = text
        self.ref_lang = lang
        logger.info(f"[SoVITS] ref_audio set: {path}")


class TTSEngine:
    """Unified TTS engine manager — wraps Edge-TTS and GPT-SoVITS."""

    def __init__(self):
        self.edge = EdgeTTSEngine()
        self.sovits = SoVITSEngine()
        self._active = self.edge  # default

    @property
    def active_engine(self):
        return self._active

    def set_engine(self, name):
        if name == "GPT-SoVITS":
            self._active = self.sovits
        else:
            self._active = self.edge
        logger.info(f"[TTS] active engine: {self._active.name}")

    def generate(self, text, output_path, **kw):
        return self._active.generate(text, output_path, **kw)

    def get_voices(self, lang="ko"):
        return self._active.get_voices(lang)

    # backward compat
    @property
    def default_voice(self):
        return getattr(self._active, "default_voice", "")

    @property
    def default_rate(self):
        return getattr(self._active, "default_rate", "+0%")
'''

path = os.path.join(BASE, "engines", "tts_engine.py")
with open(path, "w", encoding="utf-8") as f:
    f.write(tts_engine_code)
print(f"[1] OK: {path}")


# ============================================================
# 2) tts_panel.py — 완전 새로 작성
# ============================================================
tts_panel_code = r'''import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QTextEdit, QLabel, QFileDialog, QProgressBar, QGroupBox,
    QSlider, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from loguru import logger


class TTSWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engine, text, output_path, **kwargs):
        super().__init__()
        self.engine = engine
        self.text = text
        self.output_path = output_path
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.engine.generate(self.text, self.output_path, **self.kwargs)
            self.finished.emit(result)
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

        # ── Engine selector ──
        engine_grp = QGroupBox("TTS Engine")
        engine_lay = QVBoxLayout(engine_grp)

        row_eng = QHBoxLayout()
        row_eng.addWidget(QLabel("Engine:"))
        self.cmb_engine = QComboBox()
        self.cmb_engine.addItems(["Edge-TTS", "GPT-SoVITS"])
        self.cmb_engine.currentTextChanged.connect(self._on_engine_changed)
        row_eng.addWidget(self.cmb_engine)

        self.lbl_status_eng = QLabel("")
        self.lbl_status_eng.setStyleSheet("color: #888; font-size: 11px;")
        row_eng.addWidget(self.lbl_status_eng)
        engine_lay.addLayout(row_eng)
        layout.addWidget(engine_grp)

        # ── Text input ──
        layout.addWidget(QLabel("Text to Speech"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter text here...\n여기에 텍스트를 입력하세요...")
        self.text_edit.setMaximumHeight(150)
        layout.addWidget(self.text_edit)

        # ── Edge-TTS settings ──
        self.edge_group = QGroupBox("Edge-TTS Settings")
        edge_lay = QVBoxLayout(self.edge_group)

        row_voice = QHBoxLayout()
        row_voice.addWidget(QLabel("Voice:"))
        self.cmb_voice = QComboBox()
        self._populate_edge_voices()
        row_voice.addWidget(self.cmb_voice)
        edge_lay.addLayout(row_voice)

        row_rate = QHBoxLayout()
        row_rate.addWidget(QLabel("Speed:"))
        self.cmb_rate = QComboBox()
        self.cmb_rate.addItems(["-30%", "-20%", "-10%", "+0%", "+10%", "+20%", "+30%"])
        self.cmb_rate.setCurrentText("+0%")
        row_rate.addWidget(self.cmb_rate)
        edge_lay.addLayout(row_rate)
        layout.addWidget(self.edge_group)

        # ── GPT-SoVITS settings ──
        self.sovits_group = QGroupBox("GPT-SoVITS Settings")
        sovits_lay = QVBoxLayout(self.sovits_group)

        # API URL
        row_api = QHBoxLayout()
        row_api.addWidget(QLabel("API:"))
        self.txt_api_url = QLineEdit("http://127.0.0.1:9880")
        row_api.addWidget(self.txt_api_url)
        self.btn_test_api = QPushButton("Test")
        self.btn_test_api.setMaximumWidth(60)
        self.btn_test_api.clicked.connect(self._test_sovits_api)
        row_api.addWidget(self.btn_test_api)
        sovits_lay.addLayout(row_api)

        # Reference audio
        row_ref = QHBoxLayout()
        row_ref.addWidget(QLabel("Ref Audio:"))
        self.txt_ref_audio = QLineEdit("D:/GPT-SoVITS/ref_audio.wav")
        row_ref.addWidget(self.txt_ref_audio)
        self.btn_browse_ref = QPushButton("...")
        self.btn_browse_ref.setMaximumWidth(30)
        self.btn_browse_ref.clicked.connect(self._browse_ref_audio)
        row_ref.addWidget(self.btn_browse_ref)
        sovits_lay.addLayout(row_ref)

        # Ref text + lang
        row_ref_text = QHBoxLayout()
        row_ref_text.addWidget(QLabel("Ref Text:"))
        self.txt_ref_text = QLineEdit("")
        self.txt_ref_text.setPlaceholderText("(optional) text spoken in ref audio")
        row_ref_text.addWidget(self.txt_ref_text)
        sovits_lay.addLayout(row_ref_text)

        row_lang = QHBoxLayout()
        row_lang.addWidget(QLabel("Text Lang:"))
        self.cmb_text_lang = QComboBox()
        self.cmb_text_lang.addItems(["ko", "en", "ja", "zh", "yue", "auto"])
        row_lang.addWidget(self.cmb_text_lang)

        row_lang.addWidget(QLabel("Ref Lang:"))
        self.cmb_ref_lang = QComboBox()
        self.cmb_ref_lang.addItems(["ko", "en", "ja", "zh", "yue", "auto"])
        row_lang.addWidget(self.cmb_ref_lang)
        sovits_lay.addLayout(row_lang)

        # Speed slider
        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Speed:"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 200)
        self.slider_speed.setValue(100)
        self.slider_speed.setTickInterval(10)
        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        row_speed.addWidget(self.slider_speed)
        self.lbl_speed = QLabel("1.0x")
        self.lbl_speed.setMinimumWidth(40)
        row_speed.addWidget(self.lbl_speed)
        sovits_lay.addLayout(row_speed)

        self.sovits_group.setVisible(False)
        layout.addWidget(self.sovits_group)

        # ── Generate button ──
        self.btn_generate = QPushButton("Generate Audio")
        self.btn_generate.setStyleSheet(
            "QPushButton{background:#00c853;color:white;padding:10px;font-weight:bold;font-size:14px;}"
            "QPushButton:hover{background:#00e676;}"
            "QPushButton:disabled{background:#666;}")
        self.btn_generate.clicked.connect(self._on_generate)
        layout.addWidget(self.btn_generate)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #aaa;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def _populate_edge_voices(self):
        self.cmb_voice.clear()
        all_voices = {}
        for lang in ["ko", "en", "ja"]:
            all_voices.update(self.engine.edge.get_voices(lang))
        for name, vid in all_voices.items():
            self.cmb_voice.addItem(name, vid)

    def _on_engine_changed(self, name):
        self.engine.set_engine(name)
        is_sovits = (name == "GPT-SoVITS")
        self.edge_group.setVisible(not is_sovits)
        self.sovits_group.setVisible(is_sovits)

        if is_sovits:
            self.engine.sovits.api_url = self.txt_api_url.text().strip()
            if self.engine.sovits.is_available():
                self.lbl_status_eng.setText("Server connected")
                self.lbl_status_eng.setStyleSheet("color: #00c853; font-size: 11px;")
            else:
                self.lbl_status_eng.setText("Server not responding")
                self.lbl_status_eng.setStyleSheet("color: #ff5252; font-size: 11px;")
        else:
            self.lbl_status_eng.setText("")

    def _on_speed_changed(self, val):
        speed = val / 100.0
        self.lbl_speed.setText(f"{speed:.1f}x")

    def _test_sovits_api(self):
        self.engine.sovits.api_url = self.txt_api_url.text().strip()
        if self.engine.sovits.is_available():
            QMessageBox.information(self, "GPT-SoVITS", "Server connected! API is ready.")
        else:
            QMessageBox.warning(self, "GPT-SoVITS",
                "Cannot connect to GPT-SoVITS server.\n\n"
                "Start the server first:\n"
                "  cd /d D:\\GPT-SoVITS\n"
                "  .\\runtime\\python api_v2.py -a 127.0.0.1 -p 9880")

    def _browse_ref_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Reference Audio",
            "D:/GPT-SoVITS",
            "Audio Files (*.wav *.mp3 *.flac)")
        if path:
            self.txt_ref_audio.setText(path)

    def _on_generate(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.lbl_status.setText("Please enter text")
            return

        # Choose file extension
        is_sovits = (self.cmb_engine.currentText() == "GPT-SoVITS")
        ext = "wav" if is_sovits else "mp3"
        default_name = f"tts_output.{ext}"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", default_name,
            f"Audio Files (*.{ext})")
        if not path:
            return

        self.btn_generate.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Generating...")

        kwargs = {}
        if is_sovits:
            self.engine.sovits.api_url = self.txt_api_url.text().strip()
            kwargs["text_lang"] = self.cmb_text_lang.currentText()
            kwargs["ref_audio"] = self.txt_ref_audio.text().strip()
            kwargs["ref_text"] = self.txt_ref_text.text().strip()
            kwargs["ref_lang"] = self.cmb_ref_lang.currentText()
            kwargs["speed"] = self.slider_speed.value() / 100.0
        else:
            kwargs["voice"] = self.cmb_voice.currentData()
            kwargs["rate"] = self.cmb_rate.currentText()

        self._worker = TTSWorker(self.engine, text, path, **kwargs)
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
        self.lbl_status.setText(f"Error: {msg[:200]}")
        logger.error(f"[TTS] {msg}")
'''

path = os.path.join(BASE, "gui", "panels", "tts_panel.py")
with open(path, "w", encoding="utf-8") as f:
    f.write(tts_panel_code)
print(f"[2] OK: {path}")


# ============================================================
# 3) requests 설치 확인 메모
# ============================================================
print()
print("=" * 60)
print("TTS upgrade complete!")
print()
print("  [1] tts_engine.py: Edge-TTS + GPT-SoVITS dual engine")
print("  [2] tts_panel.py: Full UI with engine selector")
print()
print("Next steps:")
print("  1. pip install requests  (if not already)")
print("  2. python -m aivideostudio.main")
print()
print("  GPT-SoVITS server must be running in another CMD:")
print("    cd /d D:\\GPT-SoVITS")
print("    .\\runtime\\python api_v2.py -a 127.0.0.1 -p 9880")
print("=" * 60)
