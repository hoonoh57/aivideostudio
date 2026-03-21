from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from loguru import logger


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        layout.addWidget(self.video_widget, stretch=1)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setStyleSheet("color: #ccc; font-size: 12px; padding: 2px;")
        layout.addWidget(self.lbl_time)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self._on_seek)
        layout.addWidget(self.slider)

        controls = QHBoxLayout()
        self.btn_back = QPushButton("<<")
        self.btn_back.setFixedWidth(40)
        self.btn_back.clicked.connect(self._on_back)
        controls.addWidget(self.btn_back)

        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(60)
        self.btn_play.clicked.connect(self._on_play_pause)
        controls.addWidget(self.btn_play)

        self.btn_fwd = QPushButton(">>")
        self.btn_fwd.setFixedWidth(40)
        self.btn_fwd.clicked.connect(self._on_fwd)
        controls.addWidget(self.btn_fwd)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(50)
        self.btn_stop.clicked.connect(self._on_stop)
        controls.addWidget(self.btn_stop)

        controls.addStretch()
        layout.addLayout(controls)

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)

        self.player.durationChanged.connect(self._on_duration)
        self.player.positionChanged.connect(self._on_position)
        self.player.playbackStateChanged.connect(self._on_state)

        self.audio.setVolume(0.8)

    def load(self, file_path):
        logger.info(f"Loading: {file_path}")
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.btn_play.setText("Play")

    def _on_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_stop(self):
        self.player.stop()

    def _on_back(self):
        pos = max(0, self.player.position() - 5000)
        self.player.setPosition(pos)

    def _on_fwd(self):
        pos = min(self.player.duration(), self.player.position() + 5000)
        self.player.setPosition(pos)

    def _on_seek(self, position):
        self.player.setPosition(position)

    def _on_duration(self, duration):
        self.slider.setRange(0, duration)
        self._update_time()

    def _on_position(self, position):
        self.slider.blockSignals(True)
        self.slider.setValue(position)
        self.slider.blockSignals(False)
        self._update_time()

    def _on_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def _update_time(self):
        pos = self.player.position() // 1000
        dur = self.player.duration() // 1000
        self.lbl_time.setText(
            f"{pos // 60}:{pos % 60:02d} / {dur // 60}:{dur % 60:02d}"
        )
