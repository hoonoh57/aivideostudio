from pathlib import Path
import json
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QLabel, QTabWidget,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QAction
from loguru import logger

try:
    import pysubs2
except ImportError:
    pysubs2 = None

from aivideostudio.core.undo_manager import UndoManager
from aivideostudio.core.project import Project, Asset, Clip
from aivideostudio.utils.ffprobe import probe
from aivideostudio.engines.thumbnail_engine import ThumbnailEngine
from aivideostudio.engines.subtitle_engine import SubtitleEngine
from aivideostudio.engines.tts_engine import TTSEngine
from aivideostudio.engines.export_engine import ExportEngine
from aivideostudio.gui.menu_bar import create_menu_bar
from aivideostudio.gui.toolbar import create_toolbar
from aivideostudio.gui.shortcuts import setup_shortcuts
from aivideostudio.gui.panels.asset_panel import AssetPanel
from aivideostudio.gui.panels.preview_panel import PreviewPanel
from aivideostudio.gui.panels.timeline_panel import TimelinePanel
from aivideostudio.gui.panels.inspector_panel import InspectorPanel
from aivideostudio.gui.panels.subtitle_panel import SubtitlePanel
from aivideostudio.gui.panels.tts_panel import TTSPanel
from aivideostudio.gui.panels.export_panel import ExportPanel
from aivideostudio.core.playback_engine import TimelinePlaybackEngine
from aivideostudio.engines.waveform_engine import generate_peaks, get_cached_peaks

# Suppress harmless QFont pointSize warning from emoji rendering
import warnings as _warnings
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

def _qt_msg_filter(msg_type, context, message):
    if "setPointSize" in message and "must be greater than 0" in message:
        return  # suppress
    # Default: print to stderr
    if msg_type == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif msg_type == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif msg_type == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")

qInstallMessageHandler(_qt_msg_filter)


AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif", ".svg"}
SUBTITLE_EXTS = {".srt", ".ass", ".vtt"}

AVS_FILTER = "AIVideoStudio Project (*.avs);;All Files (*.*)"


class ThumbnailWorker(QThread):
    done = pyqtSignal(str, str)
    def __init__(self, engine, path):
        super().__init__()
        self.engine = engine
        self.path = path
    def run(self):
        r = self.engine.generate(self.path)
        if r:
            self.done.emit(self.path, r)


class ImportWorker(QThread):
    """Async file import: probe media info in background thread."""
    done = pyqtSignal(str, object)  # file_path, probe_info (or None)

    def __init__(self, file_path, ffprobe_path):
        super().__init__()
        self.file_path = file_path
        self.ffprobe_path = ffprobe_path

    def run(self):
        try:
            info = probe(self.file_path, self.ffprobe_path)
            self.done.emit(self.file_path, info)
        except Exception as e:
            from loguru import logger
            logger.error(f"Import probe failed: {e}")
            self.done.emit(self.file_path, None)




class WaveformWorker(QThread):
    """Generate waveform peaks in background."""
    done = pyqtSignal(str, object)  # file_path, peaks list

    def __init__(self, file_path, ffmpeg_path):
        super().__init__()
        self.file_path = file_path
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        try:
            peaks = generate_peaks(self.file_path, self.ffmpeg_path)
            self.done.emit(self.file_path, peaks)
        except Exception as e:
            from loguru import logger
            logger.error(f"Waveform generation failed: {e}")
            self.done.emit(self.file_path, None)

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.undo_manager = UndoManager()
        self.playback_engine = TimelinePlaybackEngine()
        self.project = Project()
        self.thumb_engine = ThumbnailEngine(config.ffmpeg_path)
        self.subtitle_engine = SubtitleEngine(config.ffmpeg_path)
        self.tts_engine = TTSEngine()
        self.export_engine = ExportEngine(config.ffmpeg_path)
        self._workers = []
        self._current_video = None
        self._project_path = None  # current .avs file path

        self.setWindowTitle("AIVideoStudio v0.5")
        self.setMinimumSize(1280, 720)
        self.resize(1920, 1080)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        hw = self.config.get_hw_accels()
        gpu_info = f"GPU: {', '.join(hw[:3])}" if hw else "GPU: CPU only"
        self.status_bar.addPermanentWidget(QLabel(gpu_info))

        menu_actions = create_menu_bar(self)
        menu_actions["undo"].triggered.connect(self._do_undo)
        menu_actions["redo"].triggered.connect(self._do_redo)
        create_toolbar(self)
        setup_shortcuts(self)
        self._setup_panels()
        self._connect_signals()
        self._setup_file_shortcuts()
        self._restore()

        if self.config.verify_ffmpeg():
            self.status_bar.showMessage("FFmpeg OK - AI Studio Ready", 5000)
        else:
            self.status_bar.showMessage("FFmpeg not found!", 10000)

    # ── Panels ──
    def _setup_panels(self):
        self.preview = PreviewPanel()
        self.setCentralWidget(self.preview)

        self.asset_panel = AssetPanel()
        self.d_media = QDockWidget("Media", self)
        self.d_media.setObjectName("d_media")
        self.d_media.setWidget(self.asset_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.d_media)

        self.timeline_panel = TimelinePanel()
        self.d_timeline = QDockWidget("Timeline", self)
        self.d_timeline.setObjectName("d_timeline")
        self.d_timeline.setWidget(self.timeline_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.d_timeline)

        right_tabs = QTabWidget()
        self.inspector_panel = InspectorPanel()
        right_tabs.addTab(self.inspector_panel, "Inspector")
        self.subtitle_panel = SubtitlePanel(self.subtitle_engine)
        right_tabs.addTab(self.subtitle_panel, "Subtitle")
        self.tts_panel = TTSPanel(self.tts_engine)
        right_tabs.addTab(self.tts_panel, "TTS")
        self.export_panel = ExportPanel(self.export_engine)
        right_tabs.addTab(self.export_panel, "Export")

        self.d_right = QDockWidget("Tools", self)
        self.d_right.setObjectName("d_tools")
        self.d_right.setWidget(right_tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.d_right)

        # Default tracks
        self.timeline_panel.add_track("Video 1", "video")
        self.timeline_panel.add_track("Video 2", "video")
        self.timeline_panel.add_track("Audio 1", "audio")
        self.timeline_panel.add_track("Audio 2", "audio")
        self.timeline_panel.add_track("Subtitle 1", "subtitle")
        self.timeline_panel.set_undo_manager(self.undo_manager)
        self.timeline_panel.canvas.set_ffmpeg_path(self.config.ffmpeg_path)
        self.preview.set_engine(self.playback_engine)
        self.preview.set_sync_callback(self._sync_timeline_to_preview)
        self.export_panel.set_playback_engine(self.playback_engine)

    # ── Signals ──
    def _connect_signals(self):
        self.timeline_panel.seek_requested.connect(self._on_timeline_seek)
        self.preview.position_changed.connect(self._on_preview_position)
        self.asset_panel.file_imported.connect(self._on_file_imported)
        self.asset_panel.file_double_clicked.connect(self.add_asset_to_timeline)
        self.timeline_panel.clip_selected.connect(self._on_clip_selected)
        self.subtitle_panel.subtitle_ready.connect(self._on_subtitle_ready)
        self.tts_panel.audio_ready.connect(self._on_tts_ready)
        self.timeline_panel.canvas.drop_requested.connect(self._on_timeline_drop)
        sc_del = QShortcut(QKeySequence("Delete"), self)
        sc_del.activated.connect(self._delete_selected_clip)
        # Go to selected clip start
        sc_home = QShortcut(QKeySequence("Home"), self)
        sc_home.activated.connect(self.timeline_panel.go_to_clip_start)
        # Go to timeline start/end
        sc_start = QShortcut(QKeySequence("Ctrl+Home"), self)
        sc_start.activated.connect(lambda: self.preview.seek_to(0))
        sc_end = QShortcut(QKeySequence("Ctrl+End"), self)
        sc_end.activated.connect(lambda: self.preview.seek_to(self.playback_engine.duration - 0.1 if self.playback_engine.duration > 0 else 0))

    def _setup_file_shortcuts(self):
        pass  # shortcuts handled by menu_bar

    # ══════════════════════════════════════════════════════════
    #  PROJECT SAVE / LOAD (.avs)
    # ══════════════════════════════════════════════════════════
    def _serialize_project(self):
        """Serialize entire project state to dict."""
        # Media files
        media_files = []
        for i in range(self.asset_panel.list_widget.count()):
            item = self.asset_panel.list_widget.item(i)
            if item:
                media_files.append(item.data(Qt.ItemDataRole.UserRole))

        # Tracks and clips
        tracks = []
        for track in self.timeline_panel.canvas.tracks:
            clips = []
            for cw in track["clips"]:
                try:
                    if not cw._alive:
                        continue
                except (RuntimeError, AttributeError):
                    continue
                cd = dict(cw.clip_data)
                # Remove non-serializable keys
                clips.append({
                    "name": cd.get("name", ""),
                    "path": cd.get("path", ""),
                    "timeline_start": cd.get("timeline_start", 0),
                    "duration": cd.get("duration", 0),
                    "in_point": cd.get("in_point", 0),
                    "out_point": cd.get("out_point", 0),
                    "source_duration": cd.get("source_duration", 0),
                    "track": cd.get("track", 0),
                    "subtitle_text": cd.get("subtitle_text", ""),
                })
            tracks.append({
                "name": track["name"],
                "type": track["type"],
                "enabled": track.get("enabled", True),
                "mute": track.get("mute", False),
                "solo": track.get("solo", False),
                "lock": track.get("lock", False),
                "visible": track.get("visible", True),
                "clips": clips,
            })

        return {
            "version": "0.4",
            "media_files": media_files,
            "tracks": tracks,
        }

    def _save_project(self):
        if self._project_path:
            self._do_save(self._project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", AVS_FILTER)
        if path:
            if not path.endswith(".avs"):
                path += ".avs"
            self._do_save(path)

    def _do_save(self, path):
        try:
            data = self._serialize_project()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._project_path = path
            self.setWindowTitle(f"AIVideoStudio v0.5 - {Path(path).name}")
            self.status_bar.showMessage(f"Saved: {path}", 5000)
            logger.info(f"Project saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            logger.error(f"Save failed: {e}")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", AVS_FILTER)
        if path:
            self._do_open(path)

    def _do_open(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", str(e))
            return

        # Clear current state
        self._clear_project()

        # Restore media files
        for fp in data.get("media_files", []):
            if Path(fp).exists():
                self.asset_panel.add_file(fp)
            else:
                logger.warning(f"Missing file: {fp}")

        # Restore tracks
        tracks_data = data.get("tracks", [])
        # Remove default tracks
        self.timeline_panel.canvas.tracks.clear()

        for ti, td in enumerate(tracks_data):
            self.timeline_panel.add_track(td["name"], td["type"])
            track = self.timeline_panel.canvas.tracks[ti]
            track["enabled"] = td.get("enabled", True)
            track["mute"] = td.get("mute", False)
            track["solo"] = td.get("solo", False)
            track["lock"] = td.get("lock", False)
            track["visible"] = td.get("visible", True)

            for cd in td.get("clips", []):
                self.timeline_panel.add_clip(ti, cd)

        self._project_path = path
        self.setWindowTitle(f"AIVideoStudio v0.5 - {Path(path).name}")
        self._sync_timeline_to_preview()
        self._refresh_subtitle_overlay()
        self.status_bar.showMessage(f"Opened: {path}", 5000)
        logger.info(f"Project opened: {path}")

    def _new_project(self):
        reply = QMessageBox.question(
            self, "New Project",
            "Discard current project and start new?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._clear_project()
            self._project_path = None
            self.setWindowTitle("AIVideoStudio v0.5")
            self.status_bar.showMessage("New project created", 3000)

    def _clear_project(self):
        """Clear all media, tracks, clips."""
        # Clear clips from all tracks
        for track in self.timeline_panel.canvas.tracks:
            for cw in list(track["clips"]):
                try:
                    cw.mark_deleted()
                    cw.hide()
                    cw.setParent(None)
                    cw.deleteLater()
                except Exception:
                    pass
            track["clips"].clear()
        self.timeline_panel.canvas.tracks.clear()
        # Re-add defaults
        self.timeline_panel.add_track("Video 1", "video")
        self.timeline_panel.add_track("Video 2", "video")
        self.timeline_panel.add_track("Audio 1", "audio")
        self.timeline_panel.add_track("Audio 2", "audio")
        self.timeline_panel.add_track("Subtitle 1", "subtitle")
        # Clear media panel
        self.asset_panel.list_widget.clear()
        self.asset_panel.lbl_count.setText("0 files")
        # Clear project assets
        self.project = Project()
        self.preview.set_subtitle_events([])

    # ══════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════
    def _find_track_index(self, track_type, start_idx=0):
        for i in range(start_idx, len(self.timeline_panel.canvas.tracks)):
            if self.timeline_panel.canvas.tracks[i]["type"] == track_type:
                return i
        return -1

    def _find_track_end(self, track_idx):
        end = 0.0
        if track_idx < 0 or track_idx >= len(self.timeline_panel.canvas.tracks):
            return end
        for cw in self.timeline_panel.canvas.tracks[track_idx]["clips"]:
            try:
                if cw._alive:
                    ce = cw.clip_data.get("timeline_start", 0) + cw.clip_data.get("duration", 0)
                    end = max(end, ce)
            except (RuntimeError, AttributeError):
                pass
        return end

    def _ensure_asset(self, file_path):
        for a in self.project.assets:
            if a.path == file_path:
                return a
        self._on_file_imported(file_path)
        for a in self.project.assets:
            if a.path == file_path:
                return a
        return None

    # ══════════════════════════════════════════════════════════
    #  CORE ACTIONS
    # ══════════════════════════════════════════════════════════
    def _do_undo(self):
        if self.undo_manager.undo():
            self.status_bar.showMessage("Undo: " + (self.undo_manager.redo_name() or ""), 3000)
            self._sync_timeline_to_preview()

    def _do_redo(self):
        if self.undo_manager.redo():
            self.status_bar.showMessage("Redo: " + (self.undo_manager.undo_name() or ""), 3000)
            self._sync_timeline_to_preview()

    def _delete_selected_clip(self):
        self.timeline_panel.canvas._delete_selected()

    # ── File import ──
    def _on_file_imported(self, file_path):
        # Async probe — don't block UI
        self.status_bar.showMessage(f"Loading: {Path(file_path).name}...", 0)
        worker = ImportWorker(file_path, self.config.ffprobe_path)
        worker.done.connect(self._on_import_done)
        self._workers.append(worker)
        worker.start()

    def _on_import_done(self, file_path, info):
        if info is None:
            self.status_bar.showMessage(f"Cannot read: {Path(file_path).name}", 5000)
            return
        asset = Asset(
            path=file_path, duration=info.duration,
            width=info.width, height=info.height, fps=info.fps,
            video_codec=info.video_codec, audio_codec=info.audio_codec,
            file_size=info.file_size, has_video=info.has_video,
            has_audio=info.has_audio)
        self.project.add_asset(asset)
        self.inspector_panel.show_asset_info(asset)
        if info.has_video or info.has_audio:
            self._current_video = file_path
            self.subtitle_panel.set_video_path(file_path)
        if info.has_video:
            self.export_panel.set_input(file_path, info.duration)
        self.status_bar.showMessage(
            f"Imported: {asset.name} ({asset.width}x{asset.height}, {asset.duration:.1f}s)", 5000)
        if info.has_video:
            w = ThumbnailWorker(self.thumb_engine, file_path)
            w.done.connect(self._on_thumb)
            self._workers.append(w)
            w.start()
        # Generate waveform for audio/video files
        if info.has_audio:
            cached = get_cached_peaks(file_path)
            if cached:
                self._apply_waveform(file_path, cached)
            else:
                ww = WaveformWorker(file_path, self.config.ffmpeg_path)
                ww.done.connect(self._on_waveform_done)
                self._workers.append(ww)
                ww.start()
        self.preview.load(file_path)

    # ── Add to timeline (double-click) ──
    def add_asset_to_timeline(self, file_path):
        asset = self._ensure_asset(file_path)
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return
        duration = asset.duration if asset.duration > 0 else 5.0
        ext = Path(file_path).suffix.lower()

        # Subtitle auto-split
        if ext in SUBTITLE_EXTS:
            track_idx = self._find_track_index("subtitle")
            if track_idx >= 0:
                count = self._auto_split_subtitle(file_path, track_idx)
                self.status_bar.showMessage(f"Subtitle: {count} lines on track {track_idx}", 5000)
                return

        if ext in AUDIO_EXTS:
            track_idx = self._find_track_index("audio")
        else:
            track_idx = self._find_track_index("video")
        if track_idx < 0:
            track_idx = 0

        end_time = self._find_track_end(track_idx)
        clip = Clip(asset_path=file_path, track_index=track_idx,
                    source_in=0.0, source_out=duration, name=asset.name)
        self.project.add_clip(clip)
        clip_dict = {
            "name": asset.name, "path": file_path,
            "timeline_start": end_time, "duration": duration,
            "in_point": 0.0, "out_point": duration,
            "source_duration": duration, "track": track_idx,
        }
        cw = self.timeline_panel.add_clip(track_idx, clip_dict)
        if cw:
            cached = get_cached_peaks(file_path)
            if cached:
                cw.set_waveform(cached)
        self._sync_timeline_to_preview()
        self.preview.seek_to(end_time)
        self.status_bar.showMessage(f"Added: {asset.name} at {end_time:.1f}s (track {track_idx})", 3000)

    # ── Drop onto timeline ──
    def _on_timeline_drop(self, file_path, track_idx, time_sec):
        asset = self._ensure_asset(file_path)
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return
        duration = asset.duration if asset.duration > 0 else 5.0
        ext = Path(file_path).suffix.lower()

        if track_idx < 0 or track_idx >= len(self.timeline_panel.canvas.tracks):
            track_idx = 0
        time_sec = max(0.0, time_sec)

        # Subtitle auto-split on subtitle track
        if ext in SUBTITLE_EXTS and self.timeline_panel.canvas.tracks[track_idx]["type"] == "subtitle":
            count = self._auto_split_subtitle(file_path, track_idx)
            self.status_bar.showMessage(f"Subtitle: {count} lines on track {track_idx}", 5000)
            return

        clip = Clip(asset_path=file_path, track_index=track_idx,
                    source_in=0.0, source_out=duration, name=asset.name)
        self.project.add_clip(clip)
        clip_dict = {
            "name": asset.name, "path": file_path,
            "timeline_start": time_sec, "duration": duration,
            "in_point": 0.0, "out_point": duration,
            "source_duration": duration, "track": track_idx,
        }
        cw = self.timeline_panel.add_clip(track_idx, clip_dict)
        if cw:
            cached = get_cached_peaks(file_path)
            if cached:
                cw.set_waveform(cached)
        self._sync_timeline_to_preview()
        self.preview.seek_to(time_sec)
        self.status_bar.showMessage(f"Dropped: {asset.name} at {time_sec:.1f}s on track {track_idx}", 3000)

    # ── Subtitle auto-split ──
    def _auto_split_subtitle(self, file_path, track_idx):
        if pysubs2 is None:
            self.status_bar.showMessage("pysubs2 not installed", 5000)
            return 0
        try:
            subs = pysubs2.load(file_path, encoding="utf-8")
        except Exception:
            try:
                subs = pysubs2.load(file_path)
            except Exception as e:
                logger.error(f"Cannot parse subtitle: {e}")
                return 0
        count = 0
        events = []
        for ev in subs.events:
            if ev.is_comment:
                continue
            start_sec = ev.start / 1000.0
            end_sec = ev.end / 1000.0
            dur = end_sec - start_sec
            if dur < 0.1:
                continue
            text = ev.plaintext.strip()
            if not text:
                continue
            clip_dict = {
                "name": text[:30] + ("..." if len(text) > 30 else ""),
                "path": file_path, "timeline_start": start_sec,
                "duration": dur, "in_point": start_sec, "out_point": end_sec,
                "source_duration": dur, "track": track_idx, "subtitle_text": text,
            }
            self.timeline_panel.add_clip(track_idx, clip_dict)
            events.append({"start": start_sec, "end": end_sec, "text": text})
            count += 1
        self.preview.set_subtitle_events(events)
        self._sync_timeline_to_preview()
        return count

    def _refresh_subtitle_overlay(self):
        events = []
        for track in self.timeline_panel.canvas.tracks:
            if track.get("type") != "subtitle" or not track.get("enabled", True):
                continue
            for cw in track["clips"]:
                try:
                    if not cw._alive: continue
                except (RuntimeError, AttributeError): continue
                cd = cw.clip_data
                events.append({
                    "start": cd.get("timeline_start", 0),
                    "end": cd.get("timeline_start", 0) + cd.get("duration", 0),
                    "text": cd.get("subtitle_text", cd.get("name", "")),
                })
        events.sort(key=lambda e: e["start"])
        self.preview.set_subtitle_events(events)

    # ── Callbacks ──
    def _on_thumb(self, fp, tp):
        self.asset_panel.set_thumbnail(fp, tp)

    def _on_clip_selected(self, clip_data):
        self.inspector_panel.show_clip_info(clip_data)
        path = clip_data.get("path", "")
        if path and Path(path).exists():
            self._current_video = path
            self.subtitle_panel.set_video_path(path)
        self._sync_timeline_to_preview()
        self._refresh_subtitle_overlay()

    def _on_subtitle_ready(self, path):
        self.export_panel.set_subtitle(path)
        track_idx = self._find_track_index("subtitle")
        if track_idx >= 0:
            count = self._auto_split_subtitle(path, track_idx)
            self.status_bar.showMessage(f"Subtitle: {Path(path).name} ({count} lines)", 5000)
        else:
            self.status_bar.showMessage(f"Subtitle ready: {Path(path).name}", 5000)

    def _on_tts_ready(self, path):
        self.asset_panel.add_file(path)
        self.status_bar.showMessage(f"TTS audio ready: {Path(path).name}", 5000)

    # ── Window state ──
    def _restore(self):
        s = QSettings("AVS", "AIVideoStudio")
        g = s.value("geometry")
        st = s.value("windowState")
        if g: self.restoreGeometry(g)
        if st: self.restoreState(st)

    # ── Timeline sync ──
    def _on_timeline_seek(self, time_sec):
        if time_sec < 0:
            # Special signal: toggle play/pause
            if self.preview._playing:
                self.preview.pause()
            else:
                self.preview.play()
            return
        self._sync_timeline_to_preview()
        self.preview.seek_to(time_sec)

    def _sync_timeline_to_preview(self):
        tracks_data = []
        for track in self.timeline_panel.canvas.tracks:
            clips = []
            for cw in track["clips"]:
                try:
                    if cw._alive: clips.append(dict(cw.clip_data))
                except (RuntimeError, AttributeError): continue
            tracks_data.append({
                "name": track["name"], "type": track["type"],
                "clips": clips,
                "enabled": track.get("enabled", True),
                "mute": track.get("mute", False),
            })
        self.playback_engine.set_tracks(tracks_data)
        self._refresh_subtitle_overlay()

    def _on_preview_position(self, time_sec):
        self.timeline_panel.canvas._playhead = time_sec
        self.timeline_panel.canvas.update()
        m, s = divmod(time_sec, 60)
        self.timeline_panel.lbl_time.setText(f"{int(m)}:{s:05.2f}")
        self.playback_engine.playhead = time_sec
        # Auto-scroll timeline to keep playhead visible
        self.timeline_panel.ensure_playhead_visible()


    def _export_subtitles_from_timeline(self):
        """Export current timeline subtitle clips as SRT/ASS file."""
        events = []
        for track in self.timeline_panel.canvas.tracks:
            if track.get("type") != "subtitle" or not track.get("enabled", True):
                continue
            for cw in track["clips"]:
                try:
                    if not cw._alive: continue
                except (RuntimeError, AttributeError): continue
                cd = cw.clip_data
                events.append({
                    "start": cd.get("timeline_start", 0),
                    "end": cd.get("timeline_start", 0) + cd.get("duration", 0),
                    "text": cd.get("subtitle_text", cd.get("name", "")),
                })
        events.sort(key=lambda e: e["start"])
        if not events:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export", "No subtitle clips on timeline.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Subtitles", "subtitles.srt",
            "SRT (*.srt);;ASS (*.ass);;All (*.*)")
        if not path:
            return
        try:
            import pysubs2
            subs = pysubs2.SSAFile()
            for ev in events:
                subs.append(pysubs2.SSAEvent(
                    start=int(ev["start"] * 1000),
                    end=int(ev["end"] * 1000),
                    text=ev["text"]))
            fmt = "ass" if path.endswith(".ass") else "srt"
            subs.save(path, format_=fmt)
            self.status_bar.showMessage(f"Subtitles exported: {Path(path).name} ({len(events)} entries)", 5000)
            logger.info(f"Subtitles exported: {path}")
        except Exception as e:
            self.status_bar.showMessage(f"Export failed: {e}", 5000)
            logger.error(f"Subtitle export failed: {e}")


    def _on_waveform_done(self, file_path, peaks):
        """Called when waveform generation completes."""
        if peaks:
            self._apply_waveform(file_path, peaks)
            logger.info(f"Waveform ready: {Path(file_path).name} ({len(peaks)} peaks)")

    def _apply_waveform(self, file_path, peaks):
        """Apply waveform peaks to all clips using this file."""
        for track in self.timeline_panel.canvas.tracks:
            for cw in track["clips"]:
                try:
                    if not cw._alive:
                        continue
                except (RuntimeError, AttributeError):
                    continue
                if cw.clip_data.get("path", "") == file_path:
                    cw.set_waveform(peaks)

    def closeEvent(self, e):
        s = QSettings("AVS", "AIVideoStudio")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        super().closeEvent(e)
