from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QLabel, QTabWidget
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
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

AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}
SUBTITLE_EXTS = {".srt", ".ass", ".vtt"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif", ".svg"}


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

        self.setWindowTitle("AIVideoStudio v0.3")
        self.setMinimumSize(1280, 720)
        self.resize(1920, 1080)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        hw = self.config.get_hw_accels()
        info = f"GPU: {', '.join(hw[:3])}" if hw else "GPU: CPU only"
        self.status_bar.addPermanentWidget(QLabel(info))

        menu_actions = create_menu_bar(self)
        menu_actions["undo"].triggered.connect(self._do_undo)
        menu_actions["redo"].triggered.connect(self._do_redo)
        create_toolbar(self)
        setup_shortcuts(self)
        self._setup_panels()
        self._connect_signals()
        self._restore()

        if self.config.verify_ffmpeg():
            self.status_bar.showMessage("FFmpeg OK - AI Studio Ready", 5000)
        else:
            self.status_bar.showMessage("FFmpeg not found!", 10000)

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

        # Create default tracks
        self.timeline_panel.add_track("Video 1", "video")
        self.timeline_panel.add_track("Video 2", "video")
        self.timeline_panel.add_track("Audio 1", "audio")
        self.timeline_panel.add_track("Audio 2", "audio")
        self.timeline_panel.add_track("Subtitle 1", "subtitle")
        self.timeline_panel.set_undo_manager(self.undo_manager)
        self.preview.set_engine(self.playback_engine)
        self.preview.set_sync_callback(self._sync_timeline_to_preview)
        self.export_panel.set_playback_engine(self.playback_engine)

    def _connect_signals(self):
        self.timeline_panel.seek_requested.connect(self._on_timeline_seek)
        self.preview.position_changed.connect(self._on_preview_position)
        self.asset_panel.file_imported.connect(self._on_file_imported)
        self.asset_panel.file_double_clicked.connect(self.add_asset_to_timeline)
        self.timeline_panel.clip_selected.connect(self._on_clip_selected)
        self.subtitle_panel.subtitle_ready.connect(self._on_subtitle_ready)
        self.tts_panel.audio_ready.connect(self._on_tts_ready)

        # Connect drop from asset panel to timeline canvas
        self.timeline_panel.canvas.drop_requested.connect(self._on_timeline_drop)

        # Delete clip
        sc_del = QShortcut(QKeySequence("Delete"), self)
        sc_del.activated.connect(self._delete_selected_clip)

    # ── helpers ──
    def _find_track_index(self, track_type, start_idx=0):
        """Find first track of given type starting from start_idx."""
        for i in range(start_idx, len(self.timeline_panel.canvas.tracks)):
            if self.timeline_panel.canvas.tracks[i]["type"] == track_type:
                return i
        return -1

    def _find_track_end(self, track_idx):
        """Find end time of last clip on a track."""
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
        """Return Asset for file_path, importing if needed."""
        for a in self.project.assets:
            if a.path == file_path:
                return a
        self._on_file_imported(file_path)
        for a in self.project.assets:
            if a.path == file_path:
                return a
        return None

    # ── core actions ──
    def _do_undo(self):
        if self.undo_manager.undo():
            name = self.undo_manager.redo_name()
            self.status_bar.showMessage("Undo: " + name, 3000)
            self._sync_timeline_to_preview()

    def _do_redo(self):
        if self.undo_manager.redo():
            name = self.undo_manager.undo_name()
            self.status_bar.showMessage("Redo: " + name, 3000)
            self._sync_timeline_to_preview()

    def _delete_selected_clip(self):
        self.timeline_panel.canvas._delete_selected()

    # ── file import ──
    def _on_file_imported(self, file_path):
        info = probe(file_path, self.config.ffprobe_path)
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
            f"Imported: {asset.name} ({asset.width}x{asset.height}, "
            f"{asset.duration:.1f}s)", 5000)
        if info.has_video:
            w = ThumbnailWorker(self.thumb_engine, file_path)
            w.done.connect(self._on_thumb)
            self._workers.append(w)
            w.start()
        self.preview.load(file_path)

    # ── add to timeline (double-click) ──
    def add_asset_to_timeline(self, file_path):
        """Double-click: auto-place on the correct track type."""
        asset = self._ensure_asset(file_path)
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return
        duration = asset.duration if asset.duration > 0 else 5.0
        ext = Path(file_path).suffix.lower()

        # Choose track by file type
        if ext in AUDIO_EXTS:
            track_idx = self._find_track_index("audio")
        elif ext in SUBTITLE_EXTS:
            track_idx = self._find_track_index("subtitle")
            if track_idx >= 0:
                count = self._auto_split_subtitle(file_path, track_idx)
                self.status_bar.showMessage(
                    f"Subtitle: {count} lines placed on track {track_idx}", 5000)
                return
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
        self.timeline_panel.add_clip(track_idx, clip_dict)
        self._sync_timeline_to_preview()
        self.preview.seek_to(end_time)
        self.status_bar.showMessage(
            f"Added to timeline: {asset.name} at {end_time:.1f}s (track {track_idx})", 3000)

    # ── drop onto timeline (drag from media panel) ──
    def _on_timeline_drop(self, file_path, track_idx, time_sec):
        """Handle drop from asset panel onto a specific track/time."""
        asset = self._ensure_asset(file_path)
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return
        duration = asset.duration if asset.duration > 0 else 5.0

        # Clamp track index
        if track_idx < 0 or track_idx >= len(self.timeline_panel.canvas.tracks):
            track_idx = 0
        time_sec = max(0.0, time_sec)

        clip = Clip(asset_path=file_path, track_index=track_idx,
                    source_in=0.0, source_out=duration, name=asset.name)
        self.project.add_clip(clip)
        clip_dict = {
            "name": asset.name, "path": file_path,
            "timeline_start": time_sec, "duration": duration,
            "in_point": 0.0, "out_point": duration,
            "source_duration": duration, "track": track_idx,
        }
        self.timeline_panel.add_clip(track_idx, clip_dict)
        self._sync_timeline_to_preview()
        self.preview.seek_to(time_sec)
        # If subtitle file dropped on subtitle track, auto-split
        ext = Path(file_path).suffix.lower()
        if ext in SUBTITLE_EXTS and self.timeline_panel.canvas.tracks[track_idx]["type"] == "subtitle":
            # Remove the single clip we just added
            if self.timeline_panel.canvas.tracks[track_idx]["clips"]:
                last = self.timeline_panel.canvas.tracks[track_idx]["clips"][-1]
                self.timeline_panel.canvas.remove_clip_widget(last)
            count = self._auto_split_subtitle(file_path, track_idx)
            self.status_bar.showMessage(
                f"Subtitle: {count} lines placed on track {track_idx}", 5000)
            return

        self.status_bar.showMessage(
            f"Dropped: {asset.name} at {time_sec:.1f}s on track {track_idx}", 3000)

    # ── thumbnail / preview / clip selection ──
    def _on_thumb(self, fp, tp):
        self.asset_panel.set_thumbnail(fp, tp)

    def _on_file_preview(self, file_path):
        self.preview.load(file_path)
        self._current_video = file_path
        self.subtitle_panel.set_video_path(file_path)
        duration = 0.0
        for a in self.project.assets:
            if a.path == file_path:
                self.inspector_panel.show_asset_info(a)
                duration = a.duration
                break
        self.export_panel.set_input(file_path, duration)
        self.status_bar.showMessage(f"Preview: {Path(file_path).name}", 3000)

    def _on_clip_selected(self, clip_data):
        self.inspector_panel.show_clip_info(clip_data)
        path = clip_data.get("path", "")
        if path and Path(path).exists():
            self._current_video = path
            self.subtitle_panel.set_video_path(path)
        self._sync_timeline_to_preview()

    def _on_subtitle_ready(self, path):
        self.export_panel.set_subtitle(path)
        # Auto-place generated subtitle on subtitle track
        track_idx = self._find_track_index("subtitle")
        if track_idx >= 0:
            count = self._auto_split_subtitle(path, track_idx)
            self.status_bar.showMessage(
                f"Subtitle ready: {Path(path).name} ({count} lines placed)", 5000)
        else:
            self.status_bar.showMessage(f"Subtitle ready: {Path(path).name}", 5000)

    def _on_tts_ready(self, path):
        self.asset_panel.add_file(path)
        self.status_bar.showMessage(f"TTS audio ready: {Path(path).name}", 5000)

    # ── window state ──
    def _restore(self):
        s = QSettings("AVS", "AIVideoStudio")
        g = s.value("geometry")
        st = s.value("windowState")
        if g:
            self.restoreGeometry(g)
        if st:
            self.restoreState(st)

    # ── timeline sync ──
    def _on_timeline_seek(self, time_sec):
        self._sync_timeline_to_preview()
        self.preview.seek_to(time_sec)

    def _sync_timeline_to_preview(self):
        tracks_data = []
        for track in self.timeline_panel.canvas.tracks:
            clips = []
            for cw in track["clips"]:
                try:
                    if cw._alive:
                        clips.append(dict(cw.clip_data))
                except (RuntimeError, AttributeError):
                    continue
            tracks_data.append({
                "name": track["name"],
                "type": track["type"],
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
        self.timeline_panel.lbl_time.setText(
            str(int(m)) + ":" + "{:05.2f}".format(s))
        self.playback_engine.playhead = time_sec


    # ── Subtitle auto-split into timeline clips ──────────────
    def _auto_split_subtitle(self, file_path, track_idx):
        """Parse SRT/ASS file and create one clip per subtitle line on the subtitle track."""
        if pysubs2 is None:
            self.status_bar.showMessage("pysubs2 not installed (pip install pysubs2)", 5000)
            return 0
        try:
            subs = pysubs2.load(file_path, encoding="utf-8")
        except Exception:
            try:
                subs = pysubs2.load(file_path)
            except Exception as e:
                logger.error(f"Cannot parse subtitle: {e}")
                self.status_bar.showMessage(f"Cannot parse subtitle: {e}", 5000)
                return 0

        count = 0
        events_for_preview = []
        for ev in subs.events:
            if ev.is_comment:
                continue
            start_sec = ev.start / 1000.0
            end_sec = ev.end / 1000.0
            duration = end_sec - start_sec
            if duration < 0.1:
                continue
            text = ev.plaintext.strip()
            if not text:
                continue

            clip_dict = {
                "name": text[:30] + ("..." if len(text) > 30 else ""),
                "path": file_path,
                "timeline_start": start_sec,
                "duration": duration,
                "in_point": start_sec,
                "out_point": end_sec,
                "source_duration": duration,
                "track": track_idx,
                "subtitle_text": text,
            }
            self.timeline_panel.add_clip(track_idx, clip_dict)
            events_for_preview.append({
                "start": start_sec,
                "end": end_sec,
                "text": text,
            })
            count += 1

        # Feed to preview for overlay
        self.preview.set_subtitle_events(events_for_preview)
        self._sync_timeline_to_preview()
        logger.info(f"Auto-split subtitle: {count} clips from {Path(file_path).name}")
        return count

    def _refresh_subtitle_overlay(self):
        """Collect all subtitle events from subtitle tracks and send to preview."""
        events = []
        for track in self.timeline_panel.canvas.tracks:
            if track.get("type") != "subtitle":
                continue
            if not track.get("enabled", True):
                continue
            for cw in track["clips"]:
                try:
                    if not cw._alive:
                        continue
                except (RuntimeError, AttributeError):
                    continue
                cd = cw.clip_data
                text = cd.get("subtitle_text", cd.get("name", ""))
                events.append({
                    "start": cd.get("timeline_start", 0),
                    "end": cd.get("timeline_start", 0) + cd.get("duration", 0),
                    "text": text,
                })
        events.sort(key=lambda e: e["start"])
        self.preview.set_subtitle_events(events)

    def closeEvent(self, e):
        s = QSettings("AVS", "AIVideoStudio")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        super().closeEvent(e)
