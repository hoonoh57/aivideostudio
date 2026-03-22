from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QLabel, QTabWidget
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from loguru import logger

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
        self.timeline_panel.add_track("Audio 1", "audio")
        self.timeline_panel.set_undo_manager(self.undo_manager)
        self.preview.set_engine(self.playback_engine)

    def _connect_signals(self):
        self.timeline_panel.seek_requested.connect(self._on_timeline_seek)
        self.preview.position_changed.connect(self._on_preview_position)


        self.asset_panel.file_imported.connect(self._on_file_imported)
        self.asset_panel.file_double_clicked.connect(self._on_file_preview)
        self.timeline_panel.clip_selected.connect(self._on_clip_selected)
        self.subtitle_panel.subtitle_ready.connect(self._on_subtitle_ready)
        self.tts_panel.audio_ready.connect(self._on_tts_ready)


        # Delete clip
        sc_del = QShortcut(QKeySequence("Delete"), self)
        sc_del.activated.connect(self._delete_selected_clip)

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
        pass  # removed old Command pattern

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

        if info.has_video:
            self._current_video = file_path
            self.subtitle_panel.set_video_path(file_path)
            self.export_panel.set_input(file_path, info.duration)

        self.status_bar.showMessage(
            f"Imported: {asset.name} ({asset.width}x{asset.height}, "
            f"{asset.duration:.1f}s)", 5000)

        if info.has_video:
            w = ThumbnailWorker(self.thumb_engine, file_path)
            w.done.connect(self._on_thumb)
            self._workers.append(w)
            w.start()

        clip = Clip(asset_path=file_path, track_index=0,
                    source_in=0.0, source_out=info.duration, name=asset.name)
        self.project.add_clip(clip)
        clip_dict = {
            "name": asset.name,
            "path": file_path,
            "timeline_start": 0.0,
            "duration": info.duration,
            "in_point": 0.0,
            "out_point": info.duration,
            "track": 0,
        }
        self.timeline_panel.add_clip(0, clip_dict)
        self._sync_timeline_to_preview()
        self.preview.seek_to(0.0)

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
            self.export_panel.set_input(path, clip_data.get("duration", 0.0))
        self._sync_timeline_to_preview()

    def _on_subtitle_ready(self, path):
        self.export_panel.set_subtitle(path)
        self.status_bar.showMessage(f"Subtitle ready: {Path(path).name}", 5000)

    def _on_tts_ready(self, path):
        self.asset_panel.add_file(path)
        self.status_bar.showMessage(f"TTS audio ready: {Path(path).name}", 5000)

    def _restore(self):
        s = QSettings("AVS", "AIVideoStudio")
        g = s.value("geometry")
        st = s.value("windowState")
        if g:
            self.restoreGeometry(g)
        if st:
            self.restoreState(st)


    def _on_timeline_seek(self, time_sec):
        """Seek preview to timeline position."""
        self._sync_timeline_to_preview()
        self.preview.seek_to(time_sec)

    def _sync_timeline_to_preview(self):
        """Sync timeline data to playback engine."""
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
            })
        self.playback_engine.set_tracks(tracks_data)

    def _on_preview_position(self, time_sec):
        """Update timeline playhead from preview position."""
        self.timeline_panel.canvas._playhead = time_sec
        self.timeline_panel.canvas.update()
        m, s = divmod(time_sec, 60)
        self.timeline_panel.lbl_time.setText(
            str(int(m)) + ":" + "{:05.2f}".format(s))
        self.playback_engine.playhead = time_sec

    def closeEvent(self, e):
        s = QSettings("AVS", "AIVideoStudio")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        super().closeEvent(e)