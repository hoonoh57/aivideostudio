import math
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QButtonGroup, QToolButton, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from loguru import logger

def _qf(name, pixel_size, weight=None):
    """Create QFont with pixel size (avoids QFont pointSize <= 0 error)."""
    f = QFont(name)
    f.setPixelSize(pixel_size)
    if weight is not None:
        f.setWeight(weight)
    return f


TRACK_HEIGHT = 40
HEADER_WIDTH = 120
RULER_HEIGHT = 26
PIXELS_PER_SECOND = 100
SNAP_THRESHOLD = 8
MIN_CLIP_WIDTH = 10
HANDLE_WIDTH = 6

CLR_BG = QColor(30, 30, 30)
CLR_TRACK = QColor(45, 45, 50)
CLR_TRACK_ALT = QColor(40, 40, 45)
CLR_TRACK_DISABLED = QColor(35, 35, 35)
CLR_RULER = QColor(50, 50, 55)
CLR_RULER_TEXT = QColor(180, 180, 180)
CLR_CLIP_VIDEO = QColor(41, 121, 255, 200)
CLR_CLIP_AUDIO = QColor(76, 175, 80, 200)
CLR_CLIP_SUBTITLE = QColor(156, 39, 176, 200)
CLR_CLIP_SELECTED = QColor(255, 193, 7, 220)
CLR_CLIP_BORDER = QColor(255, 255, 255, 100)
CLR_CLIP_TEXT = QColor(255, 255, 255)
CLR_PLAYHEAD = QColor(255, 50, 50)
CLR_SNAP = QColor(255, 255, 0, 150)
CLR_HANDLE = QColor(255, 230, 0, 200)
CLR_DISABLED_OVERLAY = QColor(0, 0, 0, 120)

_TRACK_COLORS = {"video": CLR_CLIP_VIDEO, "audio": CLR_CLIP_AUDIO, "subtitle": CLR_CLIP_SUBTITLE}
_TRACK_ICONS = {"video": "V", "audio": "A", "subtitle": "S"}


class ClipWidget(QWidget):
    clicked = pyqtSignal(object, object)
    double_clicked = pyqtSignal(object)
    moved = pyqtSignal(object)
    trimmed = pyqtSignal(object)

    def __init__(self, clip_data, pps, track_type="video", parent=None):
        super().__init__(parent)
        self.clip_data = dict(clip_data)
        self._pps = pps
        self._track_type = track_type
        self._selected = False
        self._dragging = False
        self._trimming = None
        self._drag_start = QPoint()
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_start_track = -1
        self._original_in = 0.0
        self._original_out = 0.0
        self._original_start = 0.0
        self._trim_start_global = None
        self.setMinimumHeight(TRACK_HEIGHT - 4)
        self.setMaximumHeight(TRACK_HEIGHT - 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alive = True
        self.update_geometry()

    def update_geometry(self):
        if not self._alive:
            return
        start = self.clip_data.get("timeline_start", 0.0)
        duration = self.clip_data.get("duration", 1.0)
        x = int(start * self._pps) + HEADER_WIDTH
        w = max(int(duration * self._pps), MIN_CLIP_WIDTH)
        self.setGeometry(x, self.y(), w, self.height())

    def set_pps(self, pps):
        self._pps = pps
        self.update_geometry()

    def set_selected(self, sel):
        self._selected = sel
        if self._alive:
            self.update()

    def mark_deleted(self):
        self._alive = False

    def paintEvent(self, event):
        if not self._alive:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        if self._selected:
            color = CLR_CLIP_SELECTED
        else:
            color = _TRACK_COLORS.get(self._track_type, CLR_CLIP_VIDEO)
        p.setBrush(QBrush(color))
        p.setPen(QPen(CLR_CLIP_BORDER, 1))
        p.drawRoundedRect(r, 3, 3)
        if self._selected:
            p.setBrush(QBrush(CLR_HANDLE))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(r.x(), r.y(), HANDLE_WIDTH, r.height())
            p.drawRect(r.right() - HANDLE_WIDTH, r.y(), HANDLE_WIDTH, r.height())
        p.setPen(CLR_CLIP_TEXT)
        name = Path(self.clip_data.get("name", "Clip")).stem
        dur = self.clip_data.get("duration", 0)
        label = f"{name} ({dur:.1f}s)"
        p.setFont(_qf("Segoe UI", 10))
        tr = r.adjusted(HANDLE_WIDTH + 2, 1, -HANDLE_WIDTH - 2, -1)
        p.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
        p.end()

    def _hit_handle(self, pos):
        if not self._selected:
            return None
        if pos.x() <= HANDLE_WIDTH:
            return "left"
        if pos.x() >= self.width() - HANDLE_WIDTH:
            return "right"
        return None

    def mousePressEvent(self, event):
        if not self._alive:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self, event)
            handle = self._hit_handle(event.pos())
            if handle:
                self._trimming = handle
                self._original_in = self.clip_data.get("in_point", 0.0)
                self._original_out = self.clip_data.get("out_point", self.clip_data.get("duration", 1.0))
                self._original_start = self.clip_data.get("timeline_start", 0.0)
                self._trim_start_global = event.globalPosition().toPoint()
                self._drag_start = self._trim_start_global
                self._pre_drag_data = dict(self.clip_data)
            else:
                self._dragging = True
                self._drag_start = event.globalPosition().toPoint()
                self._drag_start_x = self.x()
                self._drag_start_y = self.y()
                self._drag_start_track = self.clip_data.get("track", 0)
                self._pre_drag_data = dict(self.clip_data)
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._alive:
            return
        if self._trimming:
            if self._trim_start_global is None:
                self._trim_start_global = event.globalPosition().toPoint()
                return
            delta_px = event.globalPosition().toPoint().x() - self._trim_start_global.x()
            delta_s = delta_px / self._pps
            if self._trimming == "left":
                new_in = max(0, self._original_in + delta_s)
                new_start = self._original_start + delta_s
                if new_start < 0:
                    new_in = self._original_in - self._original_start
                    new_start = 0
                dur = self._original_out - new_in
                if dur < 0.1:
                    return
                self.clip_data["in_point"] = new_in
                self.clip_data["timeline_start"] = max(0, new_start)
                self.clip_data["duration"] = dur
            else:
                new_out = self._original_out + delta_s
                src_dur = self.clip_data.get("source_duration", 0)
                ext = Path(self.clip_data.get("path", "")).suffix.lower()
                is_image = ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                                   ".tiff", ".tif", ".webp", ".svg")
                if not is_image and src_dur > 0 and new_out > src_dur:
                    new_out = src_dur
                dur = new_out - self.clip_data.get("in_point", 0)
                if dur < 0.1:
                    return
                self.clip_data["out_point"] = new_out
                self.clip_data["duration"] = dur
            self.update_geometry()
            self.trimmed.emit(self)
            event.accept()
        elif self._dragging:
            gpos = event.globalPosition().toPoint()
            delta_x = gpos.x() - self._drag_start.x()
            delta_y = gpos.y() - self._drag_start.y()
            new_x = max(HEADER_WIDTH, self._drag_start_x + delta_x)
            new_y = self._drag_start_y + delta_y
            # Snap Y to track rows
            canvas = self.parent()
            track_idx = max(0, int((new_y - RULER_HEIGHT + TRACK_HEIGHT // 2) / TRACK_HEIGHT))
            if canvas and hasattr(canvas, 'tracks'):
                track_idx = min(track_idx, len(canvas.tracks) - 1)
                if canvas.tracks[track_idx].get("lock"):
                    track_idx = self._drag_start_track
            snapped_y = RULER_HEIGHT + track_idx * TRACK_HEIGHT + 2
            self.move(new_x, snapped_y)
            new_start = (new_x - HEADER_WIDTH) / self._pps
            self.clip_data["timeline_start"] = max(0, new_start)
            self.clip_data["track"] = track_idx
            self.moved.emit(self)
            event.accept()

    def mouseReleaseEvent(self, event):
        if not self._alive:
            return
        pre = getattr(self, '_pre_drag_data', None)
        if pre is not None:
            post = dict(self.clip_data)
            moved = abs(pre.get("timeline_start",0) - post.get("timeline_start",0)) > 0.01
            track_changed = pre.get("track", 0) != post.get("track", 0)
            trimmed = (abs(pre.get("in_point",0) - post.get("in_point",0)) > 0.01 or
                       abs(pre.get("duration",0) - post.get("duration",0)) > 0.01)
            # Move clip between tracks if needed
            if self._dragging and track_changed:
                canvas = self.parent()
                if canvas and hasattr(canvas, 'tracks'):
                    old_t = pre.get("track", 0)
                    new_t = post.get("track", 0)
                    if 0 <= old_t < len(canvas.tracks) and 0 <= new_t < len(canvas.tracks):
                        if self in canvas.tracks[old_t]["clips"]:
                            canvas.tracks[old_t]["clips"].remove(self)
                        if self not in canvas.tracks[new_t]["clips"]:
                            canvas.tracks[new_t]["clips"].append(self)
                        # Update track type for coloring
                        self._track_type = canvas.tracks[new_t]["type"]
                        self.update()
                        logger.info(f"Clip moved from track {old_t} to {new_t}")
            if (moved or trimmed or track_changed):
                canvas = self.parent()
                if canvas and hasattr(canvas, '_undo_manager') and canvas._undo_manager:
                    cid = getattr(self, '_clip_id', -1)
                    old_d = dict(pre)
                    new_d = dict(post)
                    action = "Move" if (moved or track_changed) else "Trim"
                    name = post.get("name", "clip")
                    def undo_move(c=canvas, ci=cid, od=old_d, nd=new_d):
                        for track in c.tracks:
                            for cl in list(track["clips"]):
                                try:
                                    if not cl._alive: continue
                                except RuntimeError: continue
                                if getattr(cl, '_clip_id', -1) == ci:
                                    # Move back to old track if needed
                                    ot = od.get("track", 0)
                                    nt = nd.get("track", 0)
                                    if ot != nt and 0 <= ot < len(c.tracks):
                                        if cl in c.tracks[nt]["clips"]:
                                            c.tracks[nt]["clips"].remove(cl)
                                        if cl not in c.tracks[ot]["clips"]:
                                            c.tracks[ot]["clips"].append(cl)
                                        cl._track_type = c.tracks[ot]["type"]
                                    cl.clip_data.update(od)
                                    y = RULER_HEIGHT + ot * TRACK_HEIGHT + 2
                                    cl.move(cl.x(), y)
                                    cl.update_geometry()
                                    c.update()
                                    return
                    def redo_move(c=canvas, ci=cid, od=old_d, nd=new_d):
                        for track in c.tracks:
                            for cl in list(track["clips"]):
                                try:
                                    if not cl._alive: continue
                                except RuntimeError: continue
                                if getattr(cl, '_clip_id', -1) == ci:
                                    ot = od.get("track", 0)
                                    nt = nd.get("track", 0)
                                    if ot != nt and 0 <= nt < len(c.tracks):
                                        if cl in c.tracks[ot]["clips"]:
                                            c.tracks[ot]["clips"].remove(cl)
                                        if cl not in c.tracks[nt]["clips"]:
                                            c.tracks[nt]["clips"].append(cl)
                                        cl._track_type = c.tracks[nt]["type"]
                                    cl.clip_data.update(nd)
                                    y = RULER_HEIGHT + nt * TRACK_HEIGHT + 2
                                    cl.move(cl.x(), y)
                                    cl.update_geometry()
                                    c.update()
                                    return
                    canvas._undo_manager.push(f"{action} {name}", undo_move, redo_move)
            self._pre_drag_data = None
        self._trimming = None
        self._trim_start_global = None
        self._dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self._alive:
            self.double_clicked.emit(self)
            event.accept()

    def contextMenuEvent(self, event):
        if not self._alive:
            return
        menu = QMenu(self)
        act_del = menu.addAction("Delete Clip")
        act_split = menu.addAction("Split Here")
        action = menu.exec(event.globalPos())
        if action == act_del:
            p = self.parent()
            if p and hasattr(p, "remove_clip_widget"):
                p.remove_clip_widget(self)
        elif action == act_split:
            p = self.parent()
            if p and hasattr(p, "_razor_clip_at"):
                local_x = event.pos().x()
                cut_time = self.clip_data.get("timeline_start", 0) + local_x / self._pps
                p._razor_clip_at(self, cut_time)


class TimelineCanvas(QWidget):
    playhead_moved = pyqtSignal(float)
    clip_selected = pyqtSignal(dict)
    clip_double_clicked = pyqtSignal(dict)
    seek_requested = pyqtSignal(float)
    drop_requested = pyqtSignal(str, int, float)  # file_path, track_idx, time_sec

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks = []
        self._pps = PIXELS_PER_SECOND
        self._playhead = 0.0
        self._total_duration = 30.0
        self._selected_widget = None
        self._tool = "select"
        self._snap_lines = []
        self._undo_manager = None
        self._next_clip_id = 0
        self.setMinimumHeight(RULER_HEIGHT + TRACK_HEIGHT * 4)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self._dragging_playhead = False

    def set_undo_manager(self, um):
        self._undo_manager = um

    def set_tool(self, tool):
        self._tool = tool
        logger.info(f"Tool: {tool}")
        if tool == "razor":
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def add_track(self, name, track_type="video"):
        track = {
            "name": name, "type": track_type, "clips": [],
            "mute": False, "solo": False, "lock": False,
            "visible": True, "enabled": True,
        }
        self.tracks.append(track)
        self._update_size()
        self.update()
        logger.info(f"Track added: {name} ({track_type})")
        return track

    def add_clip(self, track_index, clip_data):
        if track_index < 0 or track_index >= len(self.tracks):
            return None
        track = self.tracks[track_index]
        cw = ClipWidget(clip_data, self._pps, track["type"], self)
        y = RULER_HEIGHT + track_index * TRACK_HEIGHT + 2
        cw.move(cw.x(), y)
        cw.clicked.connect(self._on_clip_clicked)
        cw.double_clicked.connect(self._on_clip_double_clicked)
        cw.moved.connect(self._on_clip_moved)
        cw.trimmed.connect(self._on_clip_trimmed)
        cw._clip_id = self._next_clip_id
        self._next_clip_id += 1
        track["clips"].append(cw)
        cw.show()
        self._update_total_duration()
        self._update_size()
        self.update()
        return cw

    def remove_clip_widget(self, cw):
        if self._selected_widget is cw:
            self._selected_widget = None
        cw.mark_deleted()
        for track in self.tracks:
            if cw in track["clips"]:
                track["clips"].remove(cw)
                break
        cw.hide()
        cw.setParent(None)
        cw.deleteLater()
        self._update_total_duration()
        self.update()

    def _safe_deselect(self):
        if self._selected_widget is not None:
            try:
                if self._selected_widget._alive:
                    self._selected_widget.set_selected(False)
            except RuntimeError:
                pass
            self._selected_widget = None

    def _on_clip_clicked(self, cw, event):
        if not cw._alive:
            return
        for track in self.tracks:
            if cw in track["clips"] and track.get("lock"):
                return
        if self._tool == "razor":
            local_x = event.pos().x()
            cut_time = cw.clip_data.get("timeline_start", 0) + local_x / self._pps
            self._razor_clip_at(cw, cut_time)
            return
        self._safe_deselect()
        self._selected_widget = cw
        cw.set_selected(True)
        self.clip_selected.emit(cw.clip_data)

    def _on_clip_double_clicked(self, cw):
        if cw._alive:
            start = cw.clip_data.get("timeline_start", 0)
            self._playhead = start
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(start)
            self.clip_double_clicked.emit(cw.clip_data)
            self.update()

    def _on_clip_moved(self, cw):
        self._try_snap(cw)
        self._update_total_duration()
        self.update()

    def _on_clip_trimmed(self, cw):
        self._update_total_duration()
        self.update()
        if cw._alive:
            self.clip_selected.emit(cw.clip_data)

    def _try_snap(self, cw):
        self._snap_lines = []
        start = cw.clip_data.get("timeline_start", 0)
        end = start + cw.clip_data.get("duration", 0)
        targets = [0.0, self._playhead]
        for track in self.tracks:
            for other in track["clips"]:
                if other is cw or not other._alive:
                    continue
                os_ = other.clip_data.get("timeline_start", 0)
                oe = os_ + other.clip_data.get("duration", 0)
                targets.extend([os_, oe])
        for t in targets:
            if abs(start - t) * self._pps < SNAP_THRESHOLD:
                cw.clip_data["timeline_start"] = t
                cw.update_geometry()
                self._snap_lines.append(t)
                return
            if abs(end - t) * self._pps < SNAP_THRESHOLD:
                cw.clip_data["timeline_start"] = t - cw.clip_data.get("duration", 0)
                cw.update_geometry()
                self._snap_lines.append(t)
                return

    def _razor_clip_at(self, cw, cut_time):
        if not cw._alive:
            return
        start = cw.clip_data.get("timeline_start", 0)
        d = cw.clip_data.get("duration", 0)
        end = start + d
        if cut_time <= start + 0.1 or cut_time >= end - 0.1:
            return
        split_offset = cut_time - start
        in_pt = cw.clip_data.get("in_point", 0)
        name = cw.clip_data.get("name", "Clip")
        filepath = cw.clip_data.get("path", "")
        track_idx = -1
        for i, track in enumerate(self.tracks):
            if cw in track["clips"]:
                track_idx = i
                break
        if track_idx < 0:
            return
        src_dur = cw.clip_data.get("source_duration", 0)
        clip1 = {"name": name, "path": filepath, "timeline_start": start,
                 "duration": split_offset, "in_point": in_pt,
                 "out_point": in_pt + split_offset, "source_duration": src_dur, "track": track_idx}
        clip2 = {"name": name + " [R]", "path": filepath, "timeline_start": cut_time,
                 "duration": d - split_offset, "in_point": in_pt + split_offset,
                 "out_point": in_pt + d, "source_duration": src_dur, "track": track_idx}
        old_data = dict(cw.clip_data)
        old_data["_clip_id"] = getattr(cw, '_clip_id', -1)
        self._safe_deselect()
        self.remove_clip_widget(cw)
        cw1 = self.add_clip(track_idx, clip1)
        cw2 = self.add_clip(track_idx, clip2)
        if self._undo_manager:
            c1d, c2d, od = dict(clip1), dict(clip2), dict(old_data)
            ti, i1, i2 = track_idx, cw1._clip_id, cw2._clip_id
            oid = old_data.get("_clip_id", -1)
            cv = self
            def undo_split():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        if getattr(c, '_clip_id', -1) in (i1, i2):
                            cv.remove_clip_widget(c)
                r = cv.add_clip(ti, od)
                if r and oid >= 0: r._clip_id = oid
                cv.update()
            def redo_split():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        ts = c.clip_data.get("timeline_start", -1)
                        if abs(ts - od["timeline_start"]) < 0.01 and abs(c.clip_data.get("duration",0) - od["duration"]) < 0.01:
                            cv.remove_clip_widget(c)
                r1 = cv.add_clip(ti, c1d)
                r2 = cv.add_clip(ti, c2d)
                if r1: r1._clip_id = i1
                if r2: r2._clip_id = i2
                cv.update()
            self._undo_manager.push(f"Split {name}", undo_split, redo_split)
        logger.info(f"Razor at {cut_time:.2f}s: {name}")

    def _delete_selected(self):
        if self._selected_widget is None:
            return
        cw = self._selected_widget
        try:
            if not cw._alive:
                self._selected_widget = None
                return
        except RuntimeError:
            self._selected_widget = None
            return
        old_data = dict(cw.clip_data)
        track_idx = -1
        for i, track in enumerate(self.tracks):
            if cw in track["clips"]:
                track_idx = i
                break
        self.remove_clip_widget(cw)
        self._selected_widget = None
        if self._undo_manager and track_idx >= 0:
            dd, di, cv = dict(old_data), track_idx, self
            def undo_del():
                cv.add_clip(di, dd)
                cv.update()
            def redo_del():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        if c._alive and abs(c.clip_data.get("timeline_start",0) - dd.get("timeline_start",0)) < 0.01:
                            cv.remove_clip_widget(c)
                            return
            self._undo_manager.push(f"Delete {dd.get('name','clip')}", undo_del, redo_del)

    def _show_track_menu(self, track_idx, global_pos):
        """Right-click context menu on track header."""
        track = self.tracks[track_idx]
        menu = QMenu(self)

        # Enable/Disable
        enabled = track.get("enabled", True)
        act_enable = menu.addAction("Disable Track" if enabled else "Enable Track")

        # Mute/Solo/Lock
        act_mute = menu.addAction("Unmute" if track.get("mute") else "Mute")
        act_solo = menu.addAction("Unsolo" if track.get("solo") else "Solo")
        act_lock = menu.addAction("Unlock" if track.get("lock") else "Lock")

        menu.addSeparator()
        act_add_v = menu.addAction("Add Video Track")
        act_add_a = menu.addAction("Add Audio Track")
        act_add_s = menu.addAction("Add Subtitle Track")
        menu.addSeparator()
        act_del = menu.addAction("Delete Track")
        act_del.setEnabled(len(self.tracks) > 1 and len(track["clips"]) == 0)

        action = menu.exec(global_pos)
        if action == act_enable:
            track["enabled"] = not enabled
            # Gray out clips visually
            self.update()
        elif action == act_mute:
            track["mute"] = not track.get("mute", False)
            self.update()
        elif action == act_solo:
            track["solo"] = not track.get("solo", False)
            self.update()
        elif action == act_lock:
            track["lock"] = not track.get("lock", False)
            self.update()
        elif action == act_add_v:
            n = sum(1 for t in self.tracks if t["type"] == "video") + 1
            self.add_track(f"Video {n}", "video")
        elif action == act_add_a:
            n = sum(1 for t in self.tracks if t["type"] == "audio") + 1
            self.add_track(f"Audio {n}", "audio")
        elif action == act_add_s:
            n = sum(1 for t in self.tracks if t["type"] == "subtitle") + 1
            self.add_track(f"Subtitle {n}", "subtitle")
        elif action == act_del:
            if len(track["clips"]) == 0 and len(self.tracks) > 1:
                self.tracks.remove(track)
                self._reposition_all_clips()
                self._update_size()
                self.update()

    def _reposition_all_clips(self):
        """Reposition all clip widgets after track add/remove."""
        for i, track in enumerate(self.tracks):
            for cw in track["clips"]:
                if cw._alive:
                    y = RULER_HEIGHT + i * TRACK_HEIGHT + 2
                    cw.move(cw.x(), y)
                    cw.clip_data["track"] = i

    # ── Drag & Drop ──
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-aivideo-asset") or event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        file_path = ""
        if mime.hasFormat("application/x-aivideo-asset"):
            file_path = bytes(mime.data("application/x-aivideo-asset")).decode("utf-8")
        elif mime.hasText():
            file_path = mime.text()
        if not file_path:
            return
        pos = event.position()
        x, y = pos.x(), pos.y()
        track_idx = int((y - RULER_HEIGHT) / TRACK_HEIGHT)
        track_idx = max(0, min(track_idx, len(self.tracks) - 1))
        time_sec = max(0.0, (x - HEADER_WIDTH) / self._pps)
        logger.info(f"Drop: {Path(file_path).name} -> track {track_idx} at {time_sec:.1f}s")
        self.drop_requested.emit(file_path, track_idx, time_sec)
        event.acceptProposedAction()

    def _update_total_duration(self):
        max_end = 1.0
        for track in self.tracks:
            for cw in track["clips"]:
                if cw._alive:
                    e = cw.clip_data.get("timeline_start", 0) + cw.clip_data.get("duration", 0)
                    if e > max_end:
                        max_end = e
        self._total_duration = max_end + 2
        self._update_size()

    def _update_size(self):
        w = int(self._total_duration * self._pps) + HEADER_WIDTH + 200
        h = RULER_HEIGHT + len(self.tracks) * TRACK_HEIGHT + 20
        self.setMinimumSize(w, h)

    def set_zoom(self, pps):
        self._pps = pps
        for track in self.tracks:
            for cw in track["clips"]:
                if cw._alive:
                    cw.set_pps(pps)
        self._update_size()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        p.fillRect(self.rect(), CLR_BG)

        for i, track in enumerate(self.tracks):
            y = RULER_HEIGHT + i * TRACK_HEIGHT
            enabled = track.get("enabled", True)
            color = CLR_TRACK if i % 2 == 0 else CLR_TRACK_ALT
            if not enabled:
                color = CLR_TRACK_DISABLED
            p.fillRect(0, y, w, TRACK_HEIGHT, color)

            # Draw disabled overlay on clip area
            if not enabled:
                p.fillRect(HEADER_WIDTH, y, w - HEADER_WIDTH, TRACK_HEIGHT, CLR_DISABLED_OVERLAY)

            # Header
            p.setPen(CLR_RULER_TEXT if enabled else QColor(100, 100, 100))
            p.setFont(_qf("Segoe UI", 11, QFont.Weight.Bold))
            icon = _TRACK_ICONS.get(track["type"], "?")
            flags = ""
            if track.get("mute"): flags += " M"
            if track.get("solo"): flags += " S"
            if track.get("lock"): flags += " L"
            if not enabled: flags += " OFF"
            # Eye icon for visibility
            enabled = track.get("enabled", True)

            # Disabled overlay on clip area
            if not enabled:
                p.fillRect(HEADER_WIDTH, y, w - HEADER_WIDTH, TRACK_HEIGHT, CLR_DISABLED_OVERLAY)
            eye = "👁" if enabled else "ⓧ"
            p.setFont(_qf("Segoe UI Emoji", 14))
            p.setPen(QColor(200, 200, 200) if enabled else QColor(100, 60, 60))
            p.drawText(QRect(2, y, 18, TRACK_HEIGHT),
                       Qt.AlignmentFlag.AlignCenter, eye)

            # Track label (after eye icon)
            p.setPen(CLR_RULER_TEXT if enabled else QColor(100, 100, 100))
            p.setFont(_qf("Segoe UI", 11, QFont.Weight.Bold))
            label = f"{icon} {track['name']}{flags}"
            p.drawText(QRect(22, y, HEADER_WIDTH - 26, TRACK_HEIGHT),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

            # Track separator line
            p.setPen(QPen(QColor(60, 60, 65), 1))
            p.drawLine(0, y + TRACK_HEIGHT - 1, w, y + TRACK_HEIGHT - 1)

        # Ruler
        p.fillRect(HEADER_WIDTH, 0, w - HEADER_WIDTH, RULER_HEIGHT, CLR_RULER)
        p.setPen(CLR_RULER_TEXT)
        p.setFont(_qf("Segoe UI", 10))
        step = 1.0
        if self._pps < 30: step = 5.0
        elif self._pps < 60: step = 2.0
        t = 0.0
        while t <= self._total_duration:
            x = int(t * self._pps) + HEADER_WIDTH
            p.drawLine(x, RULER_HEIGHT - 8, x, RULER_HEIGHT)
            m, s = divmod(int(t), 60)
            p.drawText(x + 2, RULER_HEIGHT - 10, f"{m}:{s:02d}")
            for sub in range(1, 4):
                sx = int((t + sub * step / 4) * self._pps) + HEADER_WIDTH
                p.drawLine(sx, RULER_HEIGHT - 4, sx, RULER_HEIGHT)
            t += step

        # Snap lines
        p.setPen(QPen(CLR_SNAP, 1, Qt.PenStyle.DashLine))
        for sl in self._snap_lines:
            sx = int(sl * self._pps) + HEADER_WIDTH
            p.drawLine(sx, RULER_HEIGHT, sx, h)

        # Playhead
        px = int(self._playhead * self._pps) + HEADER_WIDTH
        p.setPen(QPen(CLR_PLAYHEAD, 2))
        p.drawLine(px, 0, px, h)
        p.setBrush(QBrush(CLR_PLAYHEAD))
        p.setPen(Qt.PenStyle.NoPen)
        tri = [QPoint(px - 6, 0), QPoint(px + 6, 0), QPoint(px, 10)]
        p.drawPolygon(tri)
        p.end()

    def mousePressEvent(self, event):
        # Eye icon click (left-click on first 20px of header)
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            if x < 20 and y >= RULER_HEIGHT:
                track_idx = (y - RULER_HEIGHT) // TRACK_HEIGHT
                if 0 <= track_idx < len(self.tracks):
                    self.tracks[track_idx]["enabled"] = not self.tracks[track_idx].get("enabled", True)
                    state = "ON" if self.tracks[track_idx]["enabled"] else "OFF"
                    logger.info(f"Track {track_idx} visibility: {state}")
                    self.update()
                    event.accept()
                    return

        if event.button() == Qt.MouseButton.RightButton:
            x, y = event.pos().x(), event.pos().y()
            if x < HEADER_WIDTH and y >= RULER_HEIGHT:
                track_idx = (y - RULER_HEIGHT) // TRACK_HEIGHT
                if 0 <= track_idx < len(self.tracks):
                    self._show_track_menu(track_idx, event.globalPosition().toPoint())
                    event.accept()
                    return
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            # Check if clicking near playhead for drag (within 10px)
            px = int(self._playhead * self._pps) + HEADER_WIDTH
            if abs(x - px) < 10 and y < RULER_HEIGHT + len(self.tracks) * TRACK_HEIGHT:
                self._dragging_playhead = True
                self._playhead = max(0, (x - HEADER_WIDTH) / self._pps)
                self.playhead_moved.emit(self._playhead)
                self.seek_requested.emit(self._playhead)
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.update()
                event.accept()
                return
            if y < RULER_HEIGHT and x > HEADER_WIDTH:
                self._dragging_playhead = True
                self._playhead = max(0, (x - HEADER_WIDTH) / self._pps)
                self.playhead_moved.emit(self._playhead)
                self.seek_requested.emit(self._playhead)
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_playhead:
            x = event.pos().x()
            t = max(0, (x - HEADER_WIDTH) / self._pps)
            t = min(t, self._total_duration)
            self._playhead = t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_playhead:
            self._dragging_playhead = False
            if self._tool != "razor":
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            # Toggle play/pause — emit signal for main window
            self.seek_requested.emit(-1.0)  # special signal: -1 = toggle play
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            step = 1.0 if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.1
            new_t = max(0, self._playhead - step)
            self._playhead = new_t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            step = 1.0 if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.1
            new_t = min(self._total_duration, self._playhead + step)
            self._playhead = new_t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Home:
            # Go to selected clip start or timeline start
            if self._selected_widget and self._selected_widget._alive:
                t = self._selected_widget.clip_data.get("timeline_start", 0)
            else:
                t = 0.0
            self._playhead = t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_End:
            self._playhead = self._total_duration
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        else:
            super().keyPressEvent(event)


class TimelinePanel(QWidget):
    clip_selected = pyqtSignal(dict)
    playhead_changed = pyqtSignal(float)
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pps = PIXELS_PER_SECOND
        self._undo_manager = None
        self._build_ui()

    def set_undo_manager(self, um):
        self._undo_manager = um
        self.canvas.set_undo_manager(um)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        tb = QHBoxLayout()
        tb.setSpacing(4)
        self.btn_select = QToolButton()
        self.btn_select.setText("Select")
        self.btn_select.setCheckable(True)
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self._set_tool("select"))
        self.btn_razor = QToolButton()
        self.btn_razor.setText("Razor")
        self.btn_razor.setCheckable(True)
        self.btn_razor.clicked.connect(lambda: self._set_tool("razor"))
        self.tool_group = QButtonGroup(self)
        self.tool_group.addButton(self.btn_select)
        self.tool_group.addButton(self.btn_razor)
        tb.addWidget(self.btn_select)
        tb.addWidget(self.btn_razor)
        tb.addSpacing(10)
        tb.addWidget(QLabel("Zoom:"))
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        tb.addWidget(self.btn_zoom_out)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self.lbl_zoom)
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        tb.addWidget(self.btn_zoom_in)
        tb.addSpacing(8)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._delete_clip)
        tb.addWidget(self.btn_delete)
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.clicked.connect(self._do_undo)
        tb.addWidget(self.btn_undo)
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.clicked.connect(self._do_redo)
        tb.addWidget(self.btn_redo)
        tb.addStretch()
        self.lbl_time = QLabel("0:00.00")
        self.lbl_time.setStyleSheet("color: #ff5252; font-size: 12px; font-weight: bold;")
        tb.addWidget(self.lbl_time)
        layout.addLayout(tb)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.canvas = TimelineCanvas(self)
        self.canvas.playhead_moved.connect(self._on_playhead)
        self.canvas.clip_selected.connect(self._on_clip_selected)
        self.canvas.clip_double_clicked.connect(self._on_clip_double_clicked)
        self.canvas.seek_requested.connect(self._on_seek)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll)

    def _set_tool(self, tool):
        self.canvas.set_tool(tool)

    def _zoom_in(self):
        self._pps = min(400, self._pps + 20)
        self.canvas.set_zoom(self._pps)
        self.lbl_zoom.setText(f"{int(self._pps)}%")

    def _zoom_out(self):
        self._pps = max(20, self._pps - 20)
        self.canvas.set_zoom(self._pps)
        self.lbl_zoom.setText(f"{int(self._pps)}%")

    def _delete_clip(self):
        self.canvas._delete_selected()

    def _do_undo(self):
        if self._undo_manager:
            self._undo_manager.undo()

    def _do_redo(self):
        if self._undo_manager:
            self._undo_manager.redo()

    def _on_playhead(self, t):
        m, s = divmod(t, 60)
        self.lbl_time.setText(f"{int(m)}:{s:05.2f}")
        self.playhead_changed.emit(t)

    def _on_clip_selected(self, clip_data):
        self.clip_selected.emit(clip_data)

    def _on_clip_double_clicked(self, clip_data):
        self.seek_requested.emit(clip_data.get("timeline_start", 0))

    def _on_seek(self, t):
        self.seek_requested.emit(t)

    def add_track(self, name, track_type="video"):
        return self.canvas.add_track(name, track_type)

    def add_clip(self, track_index, clip_data):
        return self.canvas.add_clip(track_index, clip_data)

    def get_clips(self):
        clips = []
        for track in self.canvas.tracks:
            for cw in track["clips"]:
                if cw._alive:
                    clips.append(cw.clip_data)
        return clips

    def get_first_video_clip(self):
        for track in self.canvas.tracks:
            if track["type"] == "video":
                for cw in track["clips"]:
                    if cw._alive:
                        return cw.clip_data
        return None

    def ensure_playhead_visible(self):
        """Auto-scroll so the playhead stays visible with margin."""
        if not hasattr(self, 'scroll') or not self.canvas:
            return
        px = int(self.canvas._playhead * self.canvas._pps) + HEADER_WIDTH
        scroll_bar = self.scroll.horizontalScrollBar()
        view_width = self.scroll.viewport().width()
        current_scroll = scroll_bar.value()
        margin = int(view_width * 0.15)  # 15% margin from right edge

        # If playhead is approaching right edge
        if px > current_scroll + view_width - margin:
            new_scroll = px - view_width + margin + 50
            scroll_bar.setValue(min(new_scroll, scroll_bar.maximum()))
        # If playhead goes before left edge
        elif px < current_scroll + margin:
            new_scroll = max(0, px - margin - 50)
            scroll_bar.setValue(new_scroll)

    def go_to_clip_start(self):
        """Navigate to the start of the selected clip."""
        cw = self.canvas._selected_widget
        if cw and cw._alive:
            start = cw.clip_data.get("timeline_start", 0)
            self.canvas._playhead = start
            self.canvas.playhead_moved.emit(start)
            self.canvas.seek_requested.emit(start)
            self.canvas.update()
            self.ensure_playhead_visible()

    def setFocus(self, *args):
        self.canvas.setFocus()
        if args:
            super().setFocus(*args)
        else:
            super().setFocus()
