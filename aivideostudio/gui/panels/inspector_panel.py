from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt


class InspectorPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.title = QLabel("No selection")
        self.title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ccc;")
        layout.addWidget(self.title)

        self.form = QFormLayout()
        self.form.setSpacing(6)

        self.lbl_path = QLabel("-")
        self.lbl_path.setWordWrap(True)
        self.form.addRow("Path:", self.lbl_path)

        self.lbl_duration = QLabel("-")
        self.form.addRow("Duration:", self.lbl_duration)

        self.lbl_resolution = QLabel("-")
        self.form.addRow("Resolution:", self.lbl_resolution)

        self.lbl_fps = QLabel("-")
        self.form.addRow("FPS:", self.lbl_fps)

        self.lbl_codec = QLabel("-")
        self.form.addRow("Codec:", self.lbl_codec)

        self.lbl_size = QLabel("-")
        self.form.addRow("File size:", self.lbl_size)

        layout.addLayout(self.form)
        layout.addStretch()

    def show_asset_info(self, asset):
        self.title.setText(asset.name)
        self.lbl_path.setText(asset.path)
        dur = asset.duration
        self.lbl_duration.setText(str(int(dur // 60)) + ":" + str(int(dur % 60)).zfill(2) + " (" + str(round(dur, 1)) + "s)")
        self.lbl_resolution.setText(str(asset.width) + " x " + str(asset.height))
        self.lbl_fps.setText(str(asset.fps))
        self.lbl_codec.setText("V: " + str(asset.video_codec) + "  A: " + str(asset.audio_codec))
        size_mb = asset.file_size / (1024 * 1024)
        self.lbl_size.setText(str(round(size_mb, 1)) + " MB")

    def show_clip_info(self, clip_data):
        if isinstance(clip_data, dict):
            name = clip_data.get("name", "Clip")
            path = clip_data.get("path", "")
            duration = clip_data.get("duration", 0)
            track = clip_data.get("track", 0)
            src_in = clip_data.get("in", 0)
            src_out = clip_data.get("out", 0)
        else:
            name = getattr(clip_data, "name", "Clip")
            path = getattr(clip_data, "asset_path", "")
            duration = getattr(clip_data, "source_out", 0) - getattr(clip_data, "source_in", 0)
            track = getattr(clip_data, "track_index", 0)
            src_in = getattr(clip_data, "source_in", 0)
            src_out = getattr(clip_data, "source_out", 0)
        self.title.setText(name or "Clip")
        self.lbl_path.setText(str(path))
        self.lbl_duration.setText(str(round(duration, 2)) + "s")
        self.lbl_resolution.setText("Track: " + str(track))
        self.lbl_fps.setText("In: " + str(round(src_in, 2)))
        self.lbl_codec.setText("Out: " + str(round(src_out, 2)))
        self.lbl_size.setText("-")

    def clear(self):
        self.title.setText("No selection")
        for w in [self.lbl_path, self.lbl_duration, self.lbl_resolution,
                  self.lbl_fps, self.lbl_codec, self.lbl_size]:
            w.setText("-")