"""Preview Panel — mpv-based, driven by TimelinePlaybackEngine."""
import os, sys, time as _time
from pathlib import Path as _Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QSlider, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from loguru import logger

# ── Ensure libmpv-2.dll is loadable ────────────────────────────
_root = str(_Path(__file__).resolve().parents[3])
_dll = _Path(_root) / "libmpv-2.dll"
if _dll.exists():
    os.environ["PATH"] = _root + os.pathsep + os.environ["PATH"]
    try:
        os.add_dll_directory(_root)
    except OSError:
        pass
    # Pre-load so ctypes.find_library succeeds
    import ctypes as _ctypes
    _ctypes.CDLL(str(_dll))

import mpv  # noqa: E402


class PreviewPanel(QWidget):
    """Video preview driven by a TimelinePlaybackEngine."""

    position_changed = pyqtSignal(float)   # emits timeline seconds

    # ── construction ────────────────────────────────────────────
    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._player = None
        self._playing = False
        self._active_clip = None        # dict from engine
        self._loaded_path = None        # currently loaded file
        self._gap_playing = False
        self._play_start_real = 0.0
        self._play_start_tl = 0.0
        self._file_loaded = False
        self._pending_seek = None
        self._slider_dragging = False
        self._image_playing = False   # True when playing an image clip
        self._build_ui()

    @staticmethod
    def _is_image(path: str) -> bool:
        """Check if a file is an image (not video)."""
        ext = _Path(path).suffix.lower()
        return ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff",
                        ".tif", ".webp", ".svg")

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # video container
        self._container = QWidget()
        self._container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)
        self._container.setMinimumSize(320, 180)
        self._container.setStyleSheet("background:black;")
        root.addWidget(self._container, 1)

        # time label
        self._lbl_time = QLabel("0:00.00 / 0:00.00")
        self._lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._lbl_time)

        # slider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 10000)
        self._slider.sliderPressed.connect(self._slider_pressed)
        self._slider.sliderReleased.connect(self._slider_released)
        self._slider.sliderMoved.connect(self._slider_moved)
        root.addWidget(self._slider)

        # buttons
        btn_row = QHBoxLayout()
        for label, slot in [
            ("|<", self._on_back), ("Play", self._on_play_pause),
            ("Stop", self._on_stop), (">|", self._on_forward),
        ]:
            b = QPushButton(label)
            b.setFixedWidth(50)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
            if label == "Play":
                self._btn_play = b
        btn_row.addStretch()
        root.addLayout(btn_row)

        # poll timer (30 fps)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # ── engine binding ──────────────────────────────────────────
    def set_engine(self, engine):
        self._engine = engine

    # ── mpv lifecycle ───────────────────────────────────────────
    def _ensure_player(self):
        if self._player is not None:
            return
        wid = int(self._container.winId())
        try:
            self._player = mpv.MPV(
                wid=str(wid),
                vo="direct3d",
                keep_open="yes",
                idle="yes",
                hr_seek="yes",
                log_handler=self._mpv_log,
            )
        except Exception:
            self._player = mpv.MPV(
                wid=str(wid),
                vo="direct3d",
                keep_open="yes",
                idle="yes",
                log_handler=self._mpv_log,
            )
        self._player.observe_property("time-pos", self._on_time_pos)

        @self._player.event_callback("file-loaded")
        def _on_file_loaded(evt):
            self._file_loaded = True
            if self._pending_seek is not None:
                try:
                    self._player.time_pos = self._pending_seek
                except Exception as e:
                    logger.warning(f"pending seek failed: {e}")
                self._pending_seek = None

        logger.info(f"mpv player created (wid={wid})")

    @staticmethod
    def _mpv_log(level, component, message):
        if level in ("fatal", "error"):
            logger.error(f"mpv [{component}] {message}")

    def _on_time_pos(self, _prop, value):
        """Observe callback — not used for main logic, kept for debug."""
        pass

    # ── file load + seek ────────────────────────────────────────
    def _load_file(self, path: str, seek_sec: float = 0.0,
                   pause: bool = True):
        """Load a file into mpv. If same file, just seek."""
        self._ensure_player()
        if self._loaded_path == path:
            if pause:
                self._player.pause = True
            self._do_seek(seek_sec)
            return
        self._file_loaded = False
        self._pending_seek = seek_sec if seek_sec > 0.1 else None
        self._loaded_path = path
        try:
            self._player.command("loadfile", path, "replace")
            if pause:
                self._player.pause = True
        except Exception as e:
            logger.error(f"loadfile failed: {e}")

    def _do_seek(self, sec: float, exact: bool = False):
        """Seek within current file using seek command."""
        try:
            self._player.command("seek", str(sec), "absolute", "exact")
        except Exception as e:
            logger.warning(f"seek failed: {e}")

    # ── playback control ────────────────────────────────────────
    def play(self):
        if not self._engine:
            return
        self._ensure_player()
        self._playing = True
        self._btn_play.setText("Pause")

        clip = self._engine.clip_at(self._engine.playhead)
        if clip:
            self._start_clip(clip)
        else:
            self._start_gap()

        self._timer.start()

    def pause(self):
        self._playing = False
        self._btn_play.setText("Play")
        self._gap_playing = False
        self._image_playing = False
        self._timer.stop()
        if self._player:
            try:
                self._player.pause = True
            except Exception:
                pass

    def stop(self):
        self.pause()
        if self._engine:
            self._engine.playhead = 0.0
            self._seek_to_playhead()
        self._update_ui(0.0)

    def _seek_to_playhead(self):
        """Seek preview to engine.playhead (paused)."""
        if not self._engine:
            return
        t = self._engine.playhead
        clip = self._engine.clip_at(t)
        if clip:
            path = clip.get("path", "")
            if self._is_image(path):
                self._load_file(path, 0.0, pause=True)
            else:
                src_time = clip.get("in_point", 0) + (t - clip["timeline_start"])
                self._load_file(path, src_time, pause=True)
            self._active_clip = clip
            self._gap_playing = False
            self._image_playing = False
        else:
            self._active_clip = None
            self._gap_playing = False
            self._image_playing = False
            if self._player:
                try:
                    self._player.pause = True
                except Exception:
                    pass

    # ── clip / gap start ────────────────────────────────────────
    def _start_clip(self, clip):
        """Begin playing a clip from the correct source position."""
        self._active_clip = clip
        self._gap_playing = False
        self._image_playing = False
        path = clip.get("path", "")

        if self._is_image(path):
            # Image clip: load image in mpv (paused), advance by wall-clock
            self._image_playing = True
            self._play_start_real = _time.time()
            self._play_start_tl = self._engine.playhead
            self._load_file(path, 0.0, pause=True)
            return

        src_time = clip.get("in_point", 0) + (self._engine.playhead
                                        - clip["timeline_start"])
        self._load_file(clip["path"], src_time, pause=False)
        try:
            self._player.pause = False
        except Exception:
            pass

    def _start_gap(self):
        """Begin playing through a gap (black, real-time clock)."""
        self._active_clip = None
        self._gap_playing = True
        self._play_start_real = _time.time()
        self._play_start_tl = self._engine.playhead
        if self._player:
            try:
                self._player.pause = True
            except Exception:
                pass
        logger.debug(f"GAP start tl={self._play_start_tl:.2f}")

    # ── tick (30 fps timer) ─────────────────────────────────────
    def _tick(self):
        if not self._playing or not self._engine:
            return

        # ── image clip: wall-clock based, mpv shows still image ──
        if self._image_playing and self._active_clip:
            elapsed = _time.time() - self._play_start_real
            tl_now = self._play_start_tl + elapsed
            clip = self._active_clip
            clip_end_tl = clip["timeline_start"] + clip["duration"]

            if tl_now >= clip_end_tl - 0.05:
                # image clip finished
                self._engine.playhead = clip_end_tl
                self._image_playing = False
                next_clip = self._engine.clip_at(clip_end_tl)
                if next_clip and next_clip is not clip:
                    self._start_clip(next_clip)
                elif self._engine.duration > 0 and clip_end_tl >= self._engine.duration:
                    self.pause()
                else:
                    self._start_gap()
            else:
                self._engine.playhead = tl_now
            self._update_ui(self._engine.playhead)
            return

        if self._gap_playing:
            # advance by wall-clock
            elapsed = _time.time() - self._play_start_real
            tl_now = self._play_start_tl + elapsed
            self._engine.playhead = tl_now

            # check if we reached a clip
            clip = self._engine.clip_at(tl_now)
            if clip:
                self._start_clip(clip)
            else:
                total = self._engine.duration
                if total > 0 and tl_now >= total:
                    self.pause()
            self._update_ui(tl_now)
            return

        # ── active clip playback ────────────────────────────────
        if not self._active_clip:
            self.pause()
            return

        # read mpv position
        try:
            pos = self._player.time_pos
        except Exception:
            pos = None
        if pos is None:
            return

        clip = self._active_clip
        src_pos = float(pos)
        # map back to timeline
        tl_now = clip["timeline_start"] + (src_pos - clip.get("in_point", 0))
        clip_end_tl = clip["timeline_start"] + clip["duration"]

        if tl_now >= clip_end_tl - 0.05:
            # clip finished — advance
            self._engine.playhead = clip_end_tl
            next_clip = self._engine.clip_at(clip_end_tl)
            if next_clip and next_clip is not clip:
                self._start_clip(next_clip)
            elif self._engine.duration > 0 and clip_end_tl >= self._engine.duration:
                self.pause()
            else:
                self._start_gap()
        else:
            self._engine.playhead = tl_now

        self._update_ui(self._engine.playhead)

    # ── UI helpers ──────────────────────────────────────────────
    def _update_ui(self, tl_sec: float):
        total = self._engine.duration if self._engine else 0
        if total > 0:
            self._slider.blockSignals(True)
            self._slider.setValue(int(tl_sec / total * 10000))
            self._slider.blockSignals(False)

        def _fmt(s):
            m, s2 = divmod(max(0, s), 60)
            return f"{int(m)}:{s2:05.2f}"

        self._lbl_time.setText(f"{_fmt(tl_sec)} / {_fmt(total)}")
        self.position_changed.emit(tl_sec)

    # ── slider events ───────────────────────────────────────────
    def _slider_pressed(self):
        self._slider_dragging = True

    def _slider_released(self):
        self._slider_dragging = False
        self._slider_seek(self._slider.value())

    def _slider_moved(self, value):
        if self._slider_dragging:
            self._slider_seek(value)

    def _slider_seek(self, value):
        if not self._engine:
            return
        total = self._engine.duration
        if total <= 0:
            return
        t = value / 10000.0 * total
        self._engine.playhead = t
        was_playing = self._playing
        if was_playing:
            self.pause()
        self._seek_to_playhead()
        self._update_ui(t)
        if was_playing:
            self.play()

    # ── button callbacks ────────────────────────────────────────
    def _on_play_pause(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def _on_stop(self):
        self.stop()

    def _on_back(self):
        if self._engine:
            t = max(0, self._engine.playhead - 5.0)
            self._engine.playhead = t
            self._seek_to_playhead()
            self._update_ui(t)

    def _on_forward(self):
        if self._engine:
            t = min(self._engine.duration,
                    self._engine.playhead + 5.0)
            self._engine.playhead = t
            self._seek_to_playhead()
            self._update_ui(t)

    # ── external API (called by MainWindow) ─────────────────────
    def seek_timeline(self, time_sec: float):
        """Seek preview to a specific timeline time."""
        if not self._engine:
            return
        self._engine.playhead = time_sec
        self._seek_to_playhead()
        self._update_ui(time_sec)

    def load_media(self, path: str):
        """Legacy: load a single file for preview."""
        self._ensure_player()
        self._load_file(path, 0.0, pause=True)

    # ── compatibility aliases (called by MainWindow) ──────────────
    def seek_to(self, time_sec: float):
        """Alias for seek_timeline."""
        self.seek_timeline(time_sec)

    def load(self, path: str):
        """Alias for load_media."""
        self.load_media(path)

    # ── cleanup ─────────────────────────────────────────────────
    def closeEvent(self, event):
        self._timer.stop()
        if self._player:
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None
        super().closeEvent(event)
