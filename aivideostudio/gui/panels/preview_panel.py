"""Preview Panel — mpv-based, driven by TimelinePlaybackEngine.
Supports video + audio track playback + subtitle overlay + speed control."""
import os, sys, time as _time
from pathlib import Path as _Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QSlider, QLabel, QSizePolicy,
                              QComboBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from loguru import logger

_root = str(_Path(__file__).resolve().parents[3])
_dll = _Path(_root) / "libmpv-2.dll"
if _dll.exists():
    os.environ["PATH"] = _root + os.pathsep + os.environ["PATH"]
    try:
        os.add_dll_directory(_root)
    except OSError:
        pass
    import ctypes as _ctypes
    _ctypes.CDLL(str(_dll))

import mpv  # noqa: E402

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff",
               ".tif", ".webp", ".svg"}
_AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}

SPEED_OPTIONS = ["0.25x", "0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x", "3x", "4x"]
SPEED_VALUES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]


class PreviewPanel(QWidget):
    """Video preview with audio track + subtitle overlay + speed control."""

    position_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._player = None
        self._audio_player = None
        self._playing = False
        self._active_clip = None
        self._active_audio = None
        self._loaded_path = None
        self._audio_loaded_path = None
        self._gap_playing = False
        self._play_start_real = 0.0
        self._play_start_tl = 0.0
        self._file_loaded = False
        self._pending_seek = None
        self._slider_dragging = False
        self._image_playing = False
        self._sync_callback = None
        self._speed = 1.0
        self._subtitle_events = []
        self._current_sub_text = ""
        self._build_ui()

    @staticmethod
    def _is_image(path: str) -> bool:
        return _Path(path).suffix.lower() in _IMAGE_EXTS

    @staticmethod
    def _is_audio_file(path: str) -> bool:
        return _Path(path).suffix.lower() in _AUDIO_EXTS

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # Video container with subtitle overlay
        self._video_wrapper = QWidget()
        self._video_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding,
                                          QSizePolicy.Policy.Expanding)
        self._video_wrapper.setMinimumSize(320, 180)
        self._video_wrapper.setStyleSheet("background:black;")
        self._container = QWidget(self._video_wrapper)
        self._container.setStyleSheet("background:black;")

        # Subtitle overlay label
        self._sub_label = QLabel(self._video_wrapper)
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setWordWrap(True)
        self._sub_label.setStyleSheet(
            "color: white; background: rgba(0,0,0,160); "
            "padding: 4px 12px; border-radius: 4px; "
            "font-size: 15px; font-weight: bold; font-family: 'Malgun Gothic', sans-serif;"
        )
        self._sub_label.hide()
        root.addWidget(self._video_wrapper, 1)

        # Time label
        self._lbl_time = QLabel("0:00.00 / 0:00.00")
        self._lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_time.setStyleSheet("font-size: 11px; color: #ccc;")
        root.addWidget(self._lbl_time)

        # Slider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 10000)
        self._slider.sliderPressed.connect(self._slider_pressed)
        self._slider.sliderReleased.connect(self._slider_released)
        self._slider.sliderMoved.connect(self._slider_moved)
        root.addWidget(self._slider)

        # Transport buttons - two rows
        # Row 1: Navigation
        nav_row = QHBoxLayout()
        nav_row.setSpacing(2)
        nav_btns = [
            ("\u23EE", self._go_start, "Go to Start"),
            ("\u23EA", self._skip_back, "Back 5s"),
            ("\u25B6 Play", self._on_play_pause, "Play / Pause"),
            ("\u23F9 Stop", self._on_stop, "Stop"),
            ("\u23E9", self._skip_forward, "Forward 5s"),
            ("\u23ED", self._go_end, "Go to End"),
        ]
        for label, slot, tip in nav_btns:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setMinimumWidth(55)
            b.setStyleSheet(
                "QPushButton{background:#2979ff;color:white;padding:5px 8px;"
                "font-size:12px;font-weight:bold;border-radius:3px;}"
                "QPushButton:hover{background:#448aff;}"
                "QPushButton:pressed{background:#1565c0;}")
            b.clicked.connect(slot)
            nav_row.addWidget(b)
            if "Play" in label:
                self._btn_play = b

        # Speed control
        nav_row.addSpacing(8)
        lbl_spd = QLabel("Speed:")
        lbl_spd.setStyleSheet("color:#aaa; font-size:11px;")
        nav_row.addWidget(lbl_spd)
        self._combo_speed = QComboBox()
        self._combo_speed.addItems(SPEED_OPTIONS)
        self._combo_speed.setCurrentIndex(3)  # 1x
        self._combo_speed.setFixedWidth(65)
        self._combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        nav_row.addWidget(self._combo_speed)

        nav_row.addStretch()
        root.addLayout(nav_row)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self._video_wrapper.width()
        h = self._video_wrapper.height()
        self._container.setGeometry(0, 0, w, h)
        sub_h = 50
        self._sub_label.setGeometry(20, h - sub_h - 10, w - 40, sub_h)

    # ── Speed control ──────────────────────────────────────────
    def _on_speed_changed(self, idx):
        self._speed = SPEED_VALUES[idx]
        if self._player:
            try:
                self._player.speed = self._speed
            except Exception:
                pass
        if self._audio_player:
            try:
                self._audio_player.speed = self._speed
            except Exception:
                pass
        logger.info(f"Playback speed: {self._speed}x")

    # ── Subtitle data ──────────────────────────────────────────
    def set_subtitle_events(self, events):
        self._subtitle_events = events or []
        logger.info(f"Preview: loaded {len(self._subtitle_events)} subtitle events")

    def _update_subtitle_overlay(self, tl_sec):
        text = ""
        style = {}
        for ev in self._subtitle_events:
            if ev["start"] <= tl_sec < ev["end"]:
                text = ev["text"]
                style = ev.get("style", {})
                break
        if text != self._current_sub_text:
            self._current_sub_text = text
            if text:
                self._sub_label.setText(text)
                self._apply_subtitle_style(style)
                self._sub_label.show()
            else:
                self._sub_label.hide()

    def _apply_subtitle_style(self, style):
        """Apply per-subtitle style to the overlay label."""
        if not style:
            # Default style
            self._sub_label.setStyleSheet(
                "QLabel{color:white; font-size:16px; background:rgba(0,0,0,160);"
                "padding:4px 12px; border-radius:4px;}")
            return
        font_name = style.get("font", "Malgun Gothic")
        font_size = style.get("size", 16)
        # Scale down for preview (subtitle size is for video resolution)
        preview_size = max(10, min(font_size, 28))
        fc = style.get("font_color", "#ffffff")
        oc = style.get("outline_color", "#000000")
        bold = "bold" if style.get("bold") else "normal"
        italic = "italic" if style.get("italic") else "normal"
        underline = "underline" if style.get("underline") else "none"
        bg = "rgba(0,0,0,160)" if style.get("bg_box") else "rgba(0,0,0,100)"
        outline_px = min(style.get("outline_size", 2), 3)
        shadow = f"1px 1px 2px {oc}" if style.get("shadow") else "none"
        # Alignment: adjust label alignment
        an = style.get("alignment", 2)
        if an in (1, 4, 7):
            align = "left"
        elif an in (3, 6, 9):
            align = "right"
        else:
            align = "center"
        self._sub_label.setStyleSheet(
            f"QLabel{{"
            f"color:{fc}; font-family:'{font_name}'; font-size:{preview_size}px;"
            f"font-weight:{bold}; font-style:{italic}; text-decoration:{underline};"
            f"background:{bg}; padding:4px 12px; border-radius:4px;"
            f"text-align:{align};"
            f"}}")
        if an in (1, 4, 7):
            from PyQt6.QtCore import Qt as QtC
            self._sub_label.setAlignment(QtC.AlignmentFlag.AlignLeft)
        elif an in (3, 6, 9):
            from PyQt6.QtCore import Qt as QtC
            self._sub_label.setAlignment(QtC.AlignmentFlag.AlignRight)
        else:
            from PyQt6.QtCore import Qt as QtC
            self._sub_label.setAlignment(QtC.AlignmentFlag.AlignCenter)

    # ── engine binding ──────────────────────────────────────────
    def set_engine(self, engine):
        self._engine = engine

    def set_sync_callback(self, callback):
        self._sync_callback = callback

    def _sync_before_play(self):
        if self._sync_callback:
            self._sync_callback()

    # ── mpv lifecycle ───────────────────────────────────────────
    def _ensure_player(self):
        if self._player is not None:
            return
        wid = int(self._container.winId())
        try:
            self._player = mpv.MPV(
                wid=str(wid), vo="gpu", keep_open="yes",
                idle="yes", hr_seek="yes", log_handler=self._mpv_log)
        except Exception:
            self._player = mpv.MPV(
                wid=str(wid), vo="gpu", keep_open="yes",
                idle="yes", log_handler=self._mpv_log)

        @self._player.event_callback("file-loaded")
        def _on_file_loaded(evt):
            self._file_loaded = True
            if self._pending_seek is not None:
                try:
                    self._player.command("seek", str(self._pending_seek), "absolute", "exact")
                except Exception as e:
                    logger.warning(f"pending seek failed: {e}")
                self._pending_seek = None

        logger.info(f"mpv video player created (wid={wid})")

    def _ensure_audio_player(self):
        if self._audio_player is not None:
            return
        try:
            self._audio_player = mpv.MPV(
                video="no", keep_open="yes", idle="yes",
                hr_seek="yes", log_handler=self._mpv_log)
            logger.info("mpv audio player created (headless)")
        except Exception as e:
            logger.error(f"Failed to create audio player: {e}")
            self._audio_player = None

    @staticmethod
    def _mpv_log(level, component, message):
        if level in ("fatal", "error"):
            logger.error(f"mpv [{component}] {message}")

    # ── file load + seek ────────────────────────────────────────
    def _load_file(self, path, seek_sec=0.0, pause=True):
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
            self._player.speed = self._speed
            if pause:
                self._player.pause = True
        except Exception as e:
            logger.error(f"loadfile failed: {e}")

    def _load_audio(self, path, seek_sec=0.0, pause=True):
        self._ensure_audio_player()
        if self._audio_player is None:
            return
        if self._audio_loaded_path == path:
            if pause:
                self._audio_player.pause = True
            try:
                self._audio_player.command("seek", str(seek_sec), "absolute", "exact")
            except Exception:
                pass
            return
        self._audio_loaded_path = path
        try:
            self._audio_player.command("loadfile", path, "replace")
            self._audio_player.speed = self._speed
            if pause:
                self._audio_player.pause = True
            if seek_sec > 0.1:
                import threading
                def _delayed_seek():
                    _time.sleep(0.3)
                    try:
                        self._audio_player.command("seek", str(seek_sec), "absolute", "exact")
                    except Exception:
                        pass
                threading.Thread(target=_delayed_seek, daemon=True).start()
        except Exception as e:
            logger.error(f"audio loadfile failed: {e}")

    def _stop_audio(self):
        if self._audio_player:
            try:
                self._audio_player.pause = True
            except Exception:
                pass
        self._active_audio = None
        self._audio_loaded_path = None

    def _do_seek(self, sec):
        if self._loaded_path and self._is_image(self._loaded_path):
            return
        try:
            self._player.command("seek", str(sec), "absolute", "exact")
        except Exception as e:
            logger.warning(f"seek failed: {e}")

    def _set_video_mute(self, mute):
        if self._player:
            try:
                self._player.mute = mute
            except Exception:
                pass

    def _sync_audio_for_time(self, t, playing=False):
        if not self._engine:
            return
        q = self._engine.query(t)

        # Video track mute control
        video_muted = q.get("video_muted", False)
        self._set_video_mute(video_muted)

        audio_list = q.get("audio", [])
        if audio_list:
            ai = audio_list[0]
            audio_path = ai["path"]
            audio_src_time = ai["source_time"]
            clip = ai["clip"]
            if not video_muted:
                self._set_video_mute(True)
            if self._active_audio is None or self._active_audio.get("path") != audio_path:
                self._load_audio(audio_path, audio_src_time, pause=not playing)
                self._active_audio = clip
                if playing:
                    try:
                        self._audio_player.pause = False
                    except Exception:
                        pass
            elif playing:
                try:
                    if self._audio_player.pause:
                        self._audio_player.pause = False
                except Exception:
                    pass
        else:
            if not video_muted:
                self._set_video_mute(False)
            if self._active_audio is not None:
                self._stop_audio()

    # ── playback control ────────────────────────────────────────
    def play(self):
        if not self._engine:
            return
        self._ensure_player()
        self._sync_before_play()
        self._playing = True
        self._btn_play.setText("\u23F8 Pause")
        t = self._engine.playhead
        clip = self._engine.clip_at(t)
        if clip:
            self._start_clip(clip)
        else:
            q = self._engine.query(t)
            if q.get("audio"):
                self._start_audio_only(t)
            else:
                self._start_gap()
        self._sync_audio_for_time(t, playing=True)
        self._timer.start()

    def pause(self):
        self._playing = False
        self._btn_play.setText("\u25B6 Play")
        self._gap_playing = False
        self._image_playing = False
        self._timer.stop()
        if self._player:
            try: self._player.pause = True
            except Exception: pass
        if self._audio_player:
            try: self._audio_player.pause = True
            except Exception: pass

    def stop(self):
        self.pause()
        if self._engine:
            self._engine.playhead = 0.0
            self._seek_to_playhead()
        self._update_ui(0.0)

    def _seek_to_playhead(self):
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
        else:
            self._active_clip = None
            if self._player:
                try: self._player.pause = True
                except Exception: pass
        self._gap_playing = False
        self._image_playing = False
        self._sync_audio_for_time(t, playing=False)
        self._update_subtitle_overlay(t)

    def _start_clip(self, clip):
        self._active_clip = clip
        self._gap_playing = False
        self._image_playing = False
        path = clip.get("path", "")
        if self._is_image(path):
            self._image_playing = True
            self._play_start_real = _time.time()
            self._play_start_tl = self._engine.playhead
            self._load_file(path, 0.0, pause=True)
            return
        src_time = clip.get("in_point", 0) + (self._engine.playhead - clip["timeline_start"])
        self._load_file(clip["path"], src_time, pause=False)
        try:
            self._player.pause = False
            self._player.speed = self._speed
        except Exception: pass

    def _start_gap(self):
        self._active_clip = None
        self._gap_playing = True
        self._play_start_real = _time.time()
        self._play_start_tl = self._engine.playhead
        if self._player:
            try: self._player.pause = True
            except Exception: pass

    def _start_audio_only(self, t):
        self._active_clip = None
        self._gap_playing = True
        self._play_start_real = _time.time()
        self._play_start_tl = t
        if self._player:
            try: self._player.pause = True
            except Exception: pass

    # ── tick ────────────────────────────────────────────────────
    def _tick(self):
        if not self._playing or not self._engine:
            return

        if self._image_playing and self._active_clip:
            elapsed = (_time.time() - self._play_start_real) * self._speed
            tl_now = self._play_start_tl + elapsed
            clip = self._active_clip
            clip_end = clip["timeline_start"] + clip["duration"]
            if tl_now >= clip_end - 0.05:
                self._engine.playhead = clip_end
                self._image_playing = False
                nc = self._engine.clip_at(clip_end)
                if nc and nc is not clip: self._start_clip(nc)
                elif self._engine.duration > 0 and clip_end >= self._engine.duration: self.pause()
                else: self._start_gap()
            else:
                self._engine.playhead = tl_now
            self._sync_audio_for_time(self._engine.playhead, playing=True)
            self._update_subtitle_overlay(self._engine.playhead)
            self._update_ui(self._engine.playhead)
            return

        if self._gap_playing:
            elapsed = (_time.time() - self._play_start_real) * self._speed
            tl_now = self._play_start_tl + elapsed
            self._engine.playhead = tl_now
            clip = self._engine.clip_at(tl_now)
            if clip:
                self._gap_playing = False
                self._start_clip(clip)
            elif self._engine.duration > 0 and tl_now >= self._engine.duration:
                self.pause()
            self._sync_audio_for_time(tl_now, playing=True)
            self._update_subtitle_overlay(tl_now)
            self._update_ui(tl_now)
            return

        if not self._active_clip:
            q = self._engine.query(self._engine.playhead)
            if q.get("audio"):
                self._start_audio_only(self._engine.playhead)
                return
            self.pause()
            return

        try: pos = self._player.time_pos
        except Exception: pos = None
        if pos is None:
            return

        clip = self._active_clip
        tl_now = clip["timeline_start"] + (float(pos) - clip.get("in_point", 0))
        clip_end = clip["timeline_start"] + clip["duration"]
        if tl_now >= clip_end - 0.05:
            self._engine.playhead = clip_end
            nc = self._engine.clip_at(clip_end)
            if nc and nc is not clip: self._start_clip(nc)
            elif self._engine.duration > 0 and clip_end >= self._engine.duration: self.pause()
            else: self._start_gap()
        else:
            self._engine.playhead = tl_now
        self._sync_audio_for_time(self._engine.playhead, playing=True)
        self._update_subtitle_overlay(self._engine.playhead)
        self._update_ui(self._engine.playhead)

    # ── UI ──────────────────────────────────────────────────────
    def _update_ui(self, tl_sec):
        total = self._engine.duration if self._engine else 0
        if total > 0 and not self._slider_dragging:
            self._slider.blockSignals(True)
            self._slider.setValue(int(tl_sec / total * 10000))
            self._slider.blockSignals(False)
        def _fmt(s):
            m, s2 = divmod(max(0, s), 60)
            return f"{int(m)}:{s2:05.2f}"
        self._lbl_time.setText(f"{_fmt(tl_sec)} / {_fmt(total)}")
        self.position_changed.emit(tl_sec)

    def _slider_pressed(self):
        self._slider_dragging = True
    def _slider_released(self):
        self._slider_dragging = False
        self._slider_seek(self._slider.value())
    def _slider_moved(self, value):
        if self._slider_dragging:
            self._slider_seek(value)
    def _slider_seek(self, value):
        if not self._engine: return
        total = self._engine.duration
        if total <= 0: return
        t = value / 10000.0 * total
        self._engine.playhead = t
        was = self._playing
        if was: self.pause()
        self._seek_to_playhead()
        self._update_ui(t)
        if was: self.play()

    # ── Navigation ──────────────────────────────────────────────
    def _on_play_pause(self):
        if self._playing: self.pause()
        else: self.play()

    def _on_stop(self):
        self.stop()

    def _go_start(self):
        """Go to timeline start (0:00)."""
        if self._engine:
            self._engine.playhead = 0.0
            self._seek_to_playhead()
            self._update_ui(0.0)

    def _go_end(self):
        """Go to timeline end."""
        if self._engine:
            t = max(0, self._engine.duration - 0.1)
            self._engine.playhead = t
            self._seek_to_playhead()
            self._update_ui(t)

    def _skip_back(self):
        """Skip back 5 seconds."""
        if self._engine:
            t = max(0, self._engine.playhead - 5.0)
            self._engine.playhead = t
            self._seek_to_playhead()
            self._update_ui(t)

    def _skip_forward(self):
        """Skip forward 5 seconds."""
        if self._engine:
            t = min(self._engine.duration, self._engine.playhead + 5.0)
            self._engine.playhead = t
            self._seek_to_playhead()
            self._update_ui(t)

    # ── external API ────────────────────────────────────────────
    def seek_timeline(self, time_sec):
        if not self._engine: return
        self._engine.playhead = time_sec
        self._seek_to_playhead()
        self._update_ui(time_sec)
    def load_media(self, path):
        self._ensure_player()
        self._load_file(path, 0.0, pause=True)
    def seek_to(self, time_sec):
        self.seek_timeline(time_sec)
    def load(self, path):
        self.load_media(path)

    def frame_step(self, direction=1):
        """Step exactly 1 frame forward (+1) or backward (-1) using mpv."""
        if not self._engine:
            return
        self._ensure_player()
        if self._playing:
            self.pause()
        # Use mpv frame-step for precise single frame
        try:
            if direction > 0:
                self._player.command("frame-step")
            else:
                self._player.command("frame-back-step")
        except Exception:
            pass
        # Update timeline position
        try:
            pos = self._player.time_pos
            if pos is not None and self._active_clip:
                clip = self._active_clip
                tl_now = clip["timeline_start"] + (float(pos) - clip.get("in_point", 0))
                self._engine.playhead = tl_now
                self._update_subtitle_overlay(tl_now)
                self._update_ui(tl_now)
        except Exception:
            pass

    def closeEvent(self, event):
        self._timer.stop()
        for p in (self._player, self._audio_player):
            if p:
                try: p.terminate()
                except Exception: pass
        self._player = None
        self._audio_player = None
        super().closeEvent(event)
