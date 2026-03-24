import math
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QButtonGroup, QToolButton, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from loguru import logger
from aivideostudio.engines.thumbnail_engine import FilmstripWorkerThread
import os

def _qf(name, pixel_size, weight=None):
    """Create QFont with pixel size (avoids QFont pointSize <= 0 error)."""
    f = QFont()
    f.setFamily(name)
    f.setPixelSize(max(1, pixel_size))
    if weight is not None:
        f.setWeight(weight)
    return f


TRACK_HEIGHT = 40
TRACK_HEIGHT_DEFAULT = 40
TRACK_HEIGHT_MIN = 28
TRACK_HEIGHT_MAX = 200
THUMB_MIN_HEIGHT = 28
HEADER_WIDTH = 120
RULER_HEIGHT = 26
PIXELS_PER_SECOND = 100
SNAP_THRESHOLD = 8
MIN_CLIP_WIDTH = 10
HANDLE_WIDTH = 6
DRAG_THRESHOLD = 5
FRAME_DURATION = 1.0 / 30.0

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

# Zone Bar (In/Out export range)
ZONE_BAR_HEIGHT = 24
CLR_ZONE_BAR = QColor(40, 120, 255, 140)
CLR_ZONE_HANDLE = QColor(40, 120, 255, 220)
CLR_ZONE_BORDER = QColor(60, 150, 255, 200)
ZONE_HANDLE_WIDTH = 8

CLR_SNAP = QColor(255, 255, 0, 150)
CLR_HANDLE = QColor(255, 230, 0, 200)
CLR_DISABLED_OVERLAY = QColor(0, 0, 0, 120)
CLR_WAVEFORM = QColor(220, 255, 220, 200)
CLR_WAVEFORM_VIDEO = QColor(200, 230, 255, 140)

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
        self._drag_target_track = -1
        self._original_in = 0.0
        self._original_out = 0.0
        self._original_start = 0.0
        self._trim_start_global = None
        self.setMinimumHeight(TRACK_HEIGHT_DEFAULT - 4)
        self.setMaximumHeight(TRACK_HEIGHT_DEFAULT - 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alive = True
        self._waveform_peaks = None
        self._filmstrip = None
        self._filmstrip_count = 0
        self._filmstrip_requested = False
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

    def set_waveform(self, peaks):
        self._waveform_peaks = peaks
        if self._alive:
            self.update()

    def set_filmstrip(self, pixmap, count):
        self._filmstrip = pixmap
        self._filmstrip_count = count
        self.update()

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
        # Draw waveform
        if self._waveform_peaks and (self._track_type in ("audio", "video")):
            wf_color = CLR_WAVEFORM if self._track_type == "audio" else CLR_WAVEFORM_VIDEO
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(wf_color))
            clip_in = self.clip_data.get("in_point", 0)
            clip_dur = self.clip_data.get("duration", 1)
            total_peaks = len(self._waveform_peaks)
            peaks_per_sec = 200
            start_peak = int(clip_in * peaks_per_sec)
            end_peak = int((clip_in + clip_dur) * peaks_per_sec)
            start_peak = max(0, min(start_peak, total_peaks))
            end_peak = max(start_peak, min(end_peak, total_peaks))
            visible_peaks = self._waveform_peaks[start_peak:end_peak]
            if visible_peaks:
                w_area = r.width() - 2
                h_area = r.height() - 2
                mid_y = r.y() + r.height() // 2
                n = len(visible_peaks)
                if n > w_area:
                    ratio = n / w_area
                    downsampled = []
                    for di in range(int(w_area)):
                        si = int(di * ratio)
                        ei = min(int((di + 1) * ratio), n)
                        chunk = visible_peaks[si:ei]
                        downsampled.append(max(chunk) if chunk else 0)
                    visible_peaks = downsampled
                    n = len(visible_peaks)
                step_px = w_area / max(1, n)
                bar_w = max(1, int(step_px) + 1)
                if self._track_type == "audio":
                    for j, pk in enumerate(visible_peaks):
                        if pk < 0.005:
                            continue
                        half_h = int(pk * h_area * 0.48)
                        if half_h < 1:
                            half_h = 1
                        x_pos = r.x() + 1 + int(j * step_px)
                        p.drawRect(x_pos, mid_y - half_h, bar_w, half_h * 2)
                else:
                    for j, pk in enumerate(visible_peaks):
                        if pk < 0.01:
                            continue
                        half_h = int(pk * h_area * 0.3)
                        if half_h < 1:
                            continue
                        x_pos = r.x() + 1 + int(j * step_px)
                        p.drawRect(x_pos, mid_y - half_h, bar_w, half_h * 2)
        # Filmstrip
        _thumb_left_w = 0
        _thumb_right_w = 0
        if self._track_type == 'video' and r.height() >= THUMB_MIN_HEIGHT - 6 and self._filmstrip and self._filmstrip_count > 0:
            dar = 16 / 9
            frame_h = r.height() - 4
            frame_w = int(frame_h * dar)
            sprite_w = self._filmstrip.width()
            single_w = max(1, sprite_w // self._filmstrip_count)
            single_h = self._filmstrip.height()
            x_draw = 2
            clip_w = r.width() - 4
            fi = 0
            from PyQt6.QtCore import QRect, QRectF
            while x_draw < clip_w and fi < self._filmstrip_count:
                src_rect = QRect(fi * single_w, 0, single_w, single_h)
                dst_rect = QRectF(x_draw, 2, min(frame_w, clip_w - x_draw), frame_h)
                p.drawPixmap(dst_rect, self._filmstrip, QRectF(src_rect))
                x_draw += frame_w
                fi += 1
            if fi > 0:
                last_src = QRect((fi - 1) * single_w, 0, single_w, single_h)
                while x_draw < clip_w:
                    dst_rect = QRectF(x_draw, 2, min(frame_w, clip_w - x_draw), frame_h)
                    p.drawPixmap(dst_rect, self._filmstrip, QRectF(last_src))
                    x_draw += frame_w
        p.setPen(CLR_CLIP_TEXT)
        name = Path(self.clip_data.get("name", "Clip")).stem
        dur = self.clip_data.get("duration", 0)
        label = f"{name} ({dur:.1f}s)"
        p.setFont(_qf("Segoe UI", 10))
        tr = r.adjusted(HANDLE_WIDTH + 2 + _thumb_left_w, 1,
                        -HANDLE_WIDTH - 2 - _thumb_right_w, -1)
        p.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        # ── Style badge for subtitle clips ──
        if self._track_type == "subtitle" and self.clip_data.get("style_locked"):
            badge_text = "\U0001f3a8"  # 🔒
            badge_font = p.font()
            badge_font.setPixelSize(max(10, r.height() - 6))
            p.setFont(badge_font)
            p.setPen(QPen(QColor(255, 255, 255, 200)))
            p.drawText(r.right() - 18, r.y() + 2, 16, r.height() - 4,
                       Qt.AlignmentFlag.AlignCenter, badge_text)

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
                self._dragging = False
                self._drag_pending = True
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
        elif getattr(self, "_drag_pending", False) or self._dragging:
            gpos = event.globalPosition().toPoint()
            delta_x = gpos.x() - self._drag_start.x()
            delta_y = gpos.y() - self._drag_start.y()
            if not self._dragging:
                if abs(delta_x) < DRAG_THRESHOLD and abs(delta_y) < DRAG_THRESHOLD:
                    return
                self._dragging = True
                self._drag_pending = False
            new_x = max(HEADER_WIDTH, self._drag_start_x + delta_x)
            new_y = self._drag_start_y + delta_y
            canvas = self.parent()
            target_track = self._drag_start_track
            if canvas and hasattr(canvas, '_track_at_y'):
                candidate, _ = canvas._track_at_y(new_y)
                candidate = max(0, min(candidate, len(canvas.tracks) - 1))
                src_type = canvas.tracks[self._drag_start_track]["type"] if self._drag_start_track < len(canvas.tracks) else "video"
                if (canvas.tracks[candidate]["type"] == src_type
                        and not canvas.tracks[candidate].get("lock")):
                    target_track = candidate
                else:
                    target_track = self._drag_start_track
                snapped_y = canvas._track_y(target_track) + 2
                th = canvas.tracks[target_track].get("height", TRACK_HEIGHT_DEFAULT)
                self.setMinimumHeight(th - 4)
                self.setMaximumHeight(th - 4)
            else:
                snapped_y = RULER_HEIGHT + target_track * TRACK_HEIGHT_DEFAULT + 2
            self.move(new_x, snapped_y)
            new_start = (new_x - HEADER_WIDTH) / self._pps
            self.clip_data["timeline_start"] = max(0, new_start)
            self._drag_target_track = target_track
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
            if self._dragging:
                target = getattr(self, '_drag_target_track', self._drag_start_track)
                self.clip_data["track"] = target
                post = dict(self.clip_data)
                track_changed = pre.get("track", 0) != target
                if track_changed:
                    canvas = self.parent()
                    if canvas and hasattr(canvas, 'tracks'):
                        old_t = pre.get("track", 0)
                        new_t = target
                        if 0 <= old_t < len(canvas.tracks) and 0 <= new_t < len(canvas.tracks):
                            src_type = canvas.tracks[old_t]["type"]
                            dst_type = canvas.tracks[new_t]["type"]
                            if src_type == dst_type and not canvas.tracks[new_t].get("lock"):
                                if self in canvas.tracks[old_t]["clips"]:
                                    canvas.tracks[old_t]["clips"].remove(self)
                                if self not in canvas.tracks[new_t]["clips"]:
                                    canvas.tracks[new_t]["clips"].append(self)
                                self._track_type = dst_type
                                self.update()
                                logger.info(f"Clip moved from track {old_t} to {new_t}")
                            else:
                                self.clip_data["track"] = old_t
                                post = dict(self.clip_data)
                                track_changed = False
                                snapped_y = canvas._track_y(old_t) + 2
                                self.move(self.x(), snapped_y)
                                self.update_geometry()
                                logger.info(f"Track move rejected: {src_type} -> {dst_type}")
            if (moved or trimmed or track_changed):
                canvas = self.parent()
                if canvas and hasattr(canvas, '_undo_manager') and canvas._undo_manager:
                    cid = getattr(self, '_clip_id', -1)
                    old_d, new_d = dict(pre), dict(post)
                    action = "Move" if (moved or track_changed) else "Trim"
                    name = post.get("name", "clip")
                    def undo_move(c=canvas, ci=cid, od=old_d, nd=new_d):
                        for track in c.tracks:
                            for cl in list(track["clips"]):
                                try:
                                    if not cl._alive: continue
                                except RuntimeError: continue
                                if getattr(cl, '_clip_id', -1) == ci:
                                    ot, nt = od.get("track",0), nd.get("track",0)
                                    if ot != nt and 0 <= ot < len(c.tracks):
                                        if cl in c.tracks[nt]["clips"]: c.tracks[nt]["clips"].remove(cl)
                                        if cl not in c.tracks[ot]["clips"]: c.tracks[ot]["clips"].append(cl)
                                        cl._track_type = c.tracks[ot]["type"]
                                    cl.clip_data.update(od)
                                    y = c._track_y(ot) + 2
                                    cl.move(cl.x(), y)
                                    cl.update_geometry(); c.update(); return
                    def redo_move(c=canvas, ci=cid, od=old_d, nd=new_d):
                        for track in c.tracks:
                            for cl in list(track["clips"]):
                                try:
                                    if not cl._alive: continue
                                except RuntimeError: continue
                                if getattr(cl, '_clip_id', -1) == ci:
                                    ot, nt = od.get("track",0), nd.get("track",0)
                                    if ot != nt and 0 <= nt < len(c.tracks):
                                        if cl in c.tracks[ot]["clips"]: c.tracks[ot]["clips"].remove(cl)
                                        if cl not in c.tracks[nt]["clips"]: c.tracks[nt]["clips"].append(cl)
                                        cl._track_type = c.tracks[nt]["type"]
                                    cl.clip_data.update(nd)
                                    y = c._track_y(nt) + 2
                                    cl.move(cl.x(), y)
                                    cl.update_geometry(); c.update(); return
                    canvas._undo_manager.push(f"{action} {name}", undo_move, redo_move)
            self._pre_drag_data = None
        self._trimming = None
        self._trim_start_global = None
        self._dragging = False
        self._drag_pending = False
        self._drag_target_track = -1
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self._alive:
            if self._track_type == "subtitle" and self.clip_data.get("subtitle_text"):
                p = self.parent()
                if p and hasattr(p, "_edit_subtitle_text"):
                    p._edit_subtitle_text(self)
                    event.accept()
                    return
            self.double_clicked.emit(self)
            event.accept()

    def contextMenuEvent(self, event):
        if not self._alive:
            return
        menu = QMenu(self)
        act_del = menu.addAction("Delete Clip")
        act_split = menu.addAction("Split Here")
        act_pip = None
        if self._track_type == "video":
            canvas = self.parent()
            if canvas and hasattr(canvas, 'tracks'):
                track_idx = self.clip_data.get("track", 0)
                vid_count = 0
                for ti, t in enumerate(canvas.tracks):
                    if t["type"] == "video":
                        vid_count += 1
                        if ti == track_idx:
                            break
                if vid_count > 1:
                    menu.addSeparator()
                    act_pip = menu.addAction("PIP Settings...")

        act_edit_text = None
        act_merge_next = None
        if self._track_type == "subtitle":
            menu.addSeparator()
            act_edit_text = menu.addAction("Edit Subtitle Text...")
            act_merge_next = menu.addAction("Merge with Next Subtitle")
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
                if self._track_type == "subtitle":
                    p._split_subtitle_clip(self)
                else:
                    p._razor_clip_at(self, cut_time)
        elif act_edit_text and action == act_edit_text:
            p = self.parent()
            if p and hasattr(p, "_edit_subtitle_text"):
                p._edit_subtitle_text(self)
        elif act_merge_next and action == act_merge_next:
            p = self.parent()
            if p and hasattr(p, "_merge_subtitle_clip"):
                p._merge_subtitle_clip(self)
        elif act_pip and action == act_pip:
            p = self.parent()
            if p and hasattr(p, "_edit_pip_settings"):
                p._edit_pip_settings(self)
class TimelineCanvas(QWidget):
    playhead_moved = pyqtSignal(float)
    clip_selected = pyqtSignal(dict)
    clip_double_clicked = pyqtSignal(dict)
    seek_requested = pyqtSignal(float)
    drop_requested = pyqtSignal(str, int, float)

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
        self.setMinimumHeight(RULER_HEIGHT + ZONE_BAR_HEIGHT + TRACK_HEIGHT * 4)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        # Zone (In/Out) state
        self._zone_in = 0.0
        self._zone_out = 0.0
        self._zone_enabled = False
        self._dragging_zone_in = False
        self._dragging_zone_out = False
        self._zone_visible = True
        self._dragging_playhead = False
        self._resizing_track = -1
        self._resize_start_y = 0
        self._resize_start_h = 0
        self._ffmpeg_path = "ffmpeg"

    def set_undo_manager(self, um):
        self._undo_manager = um

    # Zone (In/Out) API
    def get_zone(self):
        return self._zone_in, self._zone_out, self._zone_enabled

    def set_zone(self, in_sec, out_sec):
        self._zone_in = max(0.0, in_sec)
        self._zone_out = max(0.0, out_sec)
        self._zone_enabled = (self._zone_out > self._zone_in + 0.05)
        self.update()

    def clear_zone(self):
        self._zone_in = 0.0
        self._zone_out = 0.0
        self._zone_enabled = False
        self.update()

    def _zone_bar_rect(self):
        return QRect(HEADER_WIDTH, RULER_HEIGHT,
                     self.width() - HEADER_WIDTH, ZONE_BAR_HEIGHT)

    def _zone_in_handle_rect(self):
        x = int(self._zone_in * self._pps) + HEADER_WIDTH
        y = RULER_HEIGHT
        return QRect(x - ZONE_HANDLE_WIDTH // 2, y,
                     ZONE_HANDLE_WIDTH, ZONE_BAR_HEIGHT)

    def _zone_out_handle_rect(self):
        out = self._zone_out if self._zone_out > 0 else self._total_duration
        x = int(out * self._pps) + HEADER_WIDTH
        y = RULER_HEIGHT
        return QRect(x - ZONE_HANDLE_WIDTH // 2, y,
                     ZONE_HANDLE_WIDTH, ZONE_BAR_HEIGHT)

    def set_ffmpeg_path(self, path):
        self._ffmpeg_path = path or "ffmpeg"

    def _track_y(self, idx):
        y = RULER_HEIGHT + ZONE_BAR_HEIGHT
        for i in range(min(idx, len(self.tracks))):
            y += self.tracks[i].get("height", TRACK_HEIGHT_DEFAULT)
        return y

    def _track_at_y(self, y):
        cy = RULER_HEIGHT + ZONE_BAR_HEIGHT
        for i, track in enumerate(self.tracks):
            th = track.get("height", TRACK_HEIGHT_DEFAULT)
            if cy <= y < cy + th:
                return i, y - cy
            cy += th
        return len(self.tracks) - 1, 0

    def _total_tracks_height(self):
        return sum(t.get("height", TRACK_HEIGHT_DEFAULT) for t in self.tracks)

    def _near_track_separator(self, py, threshold=5):
        y = RULER_HEIGHT + ZONE_BAR_HEIGHT
        for i, t in enumerate(self.tracks):
            y += t.get("height", TRACK_HEIGHT_DEFAULT)
            if abs(py - y) <= threshold:
                return i
        return -1

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
            "height": TRACK_HEIGHT_DEFAULT,
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
        y = self._track_y(track_index) + 2
        th = track.get("height", TRACK_HEIGHT_DEFAULT)
        cw.setMinimumHeight(th - 4)
        cw.setMaximumHeight(th - 4)
        cw.move(cw.x(), y)
        cw.clicked.connect(self._on_clip_clicked)
        cw.double_clicked.connect(self._on_clip_double_clicked)
        cw.moved.connect(self._on_clip_moved)
        cw.trimmed.connect(self._on_clip_trimmed)
        cw._clip_id = self._next_clip_id
        self._next_clip_id += 1
        track["clips"].append(cw)
        cw.show()
        if track["type"] == "video" and clip_data.get("path"):
            self._request_thumbnails(cw)
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
            if cw._track_type == "subtitle" and cw.clip_data.get("subtitle_text"):
                self._edit_subtitle_text(cw)
            else:
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
            if cw._track_type == "subtitle":
                self._notify_subtitle_changed()

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

    # Subtitle Editing Methods
    def _edit_pip_settings(self, cw):
        """Open PIP settings dialog for overlay video clips."""
        pip = cw.clip_data.get("pip", {})
        from PyQt6.QtWidgets import (QDialog, QFormLayout, QSpinBox,
                                     QDoubleSpinBox, QDialogButtonBox)

        dlg = QDialog(self.window())
        dlg.setWindowTitle("PIP Settings")
        dlg.setMinimumWidth(300)
        form = QFormLayout(dlg)

        spin_x = QSpinBox()
        spin_x.setRange(-1, 3840)
        spin_x.setValue(pip.get("x", -1))
        spin_x.setSpecialValueText("Auto (right)")
        form.addRow("X Position:", spin_x)

        spin_y = QSpinBox()
        spin_y.setRange(-1, 2160)
        spin_y.setValue(pip.get("y", -1))
        spin_y.setSpecialValueText("Auto (bottom)")
        form.addRow("Y Position:", spin_y)

        spin_w = QSpinBox()
        spin_w.setRange(0, 1920)
        spin_w.setValue(pip.get("w", 0))
        spin_w.setSpecialValueText("Auto (1/4)")
        form.addRow("Width:", spin_w)

        spin_h = QSpinBox()
        spin_h.setRange(0, 1080)
        spin_h.setValue(pip.get("h", 0))
        spin_h.setSpecialValueText("Auto (1/4)")
        form.addRow("Height:", spin_h)

        spin_opacity = QDoubleSpinBox()
        spin_opacity.setRange(0.0, 1.0)
        spin_opacity.setSingleStep(0.1)
        spin_opacity.setValue(pip.get("opacity", 1.0))
        form.addRow("Opacity:", spin_opacity)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_pip = {}
            if spin_x.value() >= 0:
                new_pip["x"] = spin_x.value()
            if spin_y.value() >= 0:
                new_pip["y"] = spin_y.value()
            if spin_w.value() > 0:
                new_pip["w"] = spin_w.value()
            if spin_h.value() > 0:
                new_pip["h"] = spin_h.value()
            new_pip["opacity"] = spin_opacity.value()
            cw.clip_data["pip"] = new_pip
            cw.update()
            logger.info(f"PIP settings updated: {new_pip}")

    def _edit_subtitle_text(self, cw):
        from aivideostudio.gui.dialogs.subtitle_edit_dialog import SubtitleEditDialog
        from PyQt6.QtWidgets import QApplication
        win = None
        for w in QApplication.topLevelWidgets():
            if hasattr(w, 'timeline_panel'):
                win = w; break
        if win is None:
            win = self.window()
        has_next = False
        track_idx = -1
        for i, track in enumerate(self.tracks):
            if cw in track["clips"]:
                track_idx = i; break
        if track_idx >= 0:
            cw_start = cw.clip_data.get("timeline_start", 0)
            for other in self.tracks[track_idx]["clips"]:
                if other is cw or not other._alive: continue
                if other.clip_data.get("timeline_start", 0) > cw_start:
                    has_next = True; break
        # Collect existing styles from all subtitle clips
        existing_styles = []
        for track in self.tracks:
            if track.get("type") != "subtitle":
                continue
            for other_cw in track["clips"]:
                try:
                    if not other_cw._alive: continue
                except (RuntimeError, AttributeError): continue
                existing_styles.append(dict(other_cw.clip_data.get("subtitle_style", {})))
        dlg = SubtitleEditDialog(cw.clip_data, has_next=has_next,
                                 existing_styles=existing_styles, parent=win)
        if dlg.exec() != SubtitleEditDialog.DialogCode.Accepted:
            return
        action = dlg.result_action
        data = dlg.result_data
        if action == "edit":
            old_text = cw.clip_data.get("subtitle_text", "")
            old_name = cw.clip_data.get("name", "")
            old_style = dict(cw.clip_data.get("subtitle_style", {}))
            old_locked = cw.clip_data.get("style_locked", False)
            new_text = data["text"]
            new_style = data["style"]
            cw.clip_data["subtitle_text"] = new_text
            cw.clip_data["name"] = new_text[:30] + ("..." if len(new_text) > 30 else "")
            cw.clip_data["subtitle_style"] = new_style
            cw.clip_data["style_locked"] = data.get("locked", False)
            cw.update()
            self._notify_subtitle_changed()
            if self._undo_manager:
                cid = getattr(cw, '_clip_id', -1)
                cv = self
                _ot, _on, _os, _ol = old_text, old_name, old_style, old_locked
                _nt, _nn, _ns, _nl = new_text, cw.clip_data["name"], dict(new_style), data.get("locked", False)
                def undo_edit():
                    for t in cv.tracks:
                        for c in t["clips"]:
                            try:
                                if not c._alive: continue
                            except RuntimeError: continue
                            if getattr(c, '_clip_id', -1) == cid:
                                c.clip_data["subtitle_text"] = _ot
                                c.clip_data["name"] = _on
                                c.clip_data["subtitle_style"] = dict(_os)
                                c.clip_data["style_locked"] = _ol
                                c.update(); cv._notify_subtitle_changed(); return
                def redo_edit():
                    for t in cv.tracks:
                        for c in t["clips"]:
                            try:
                                if not c._alive: continue
                            except RuntimeError: continue
                            if getattr(c, '_clip_id', -1) == cid:
                                c.clip_data["subtitle_text"] = _nt
                                c.clip_data["name"] = _nn
                                c.clip_data["subtitle_style"] = dict(_ns)
                                c.clip_data["style_locked"] = _nl
                                c.update(); cv._notify_subtitle_changed(); return
                self._undo_manager.push("Edit subtitle", undo_edit, redo_edit)
        elif action == "reset_all":
            # Reset ALL subtitle clips to default (skip locked)
            new_text = data["text"]
            default_style = data["style"]
            locked_flag = data.get("locked", False)
            # Save lock state for current clip
            cw.clip_data["style_locked"] = locked_flag
            if not locked_flag:
                cw.clip_data["subtitle_text"] = new_text
                cw.clip_data["name"] = new_text[:30] + ("..." if len(new_text) > 30 else "")
                cw.clip_data["subtitle_style"] = dict(default_style)
                cw.update()
            count = 0
            for track in self.tracks:
                if track.get("type") != "subtitle":
                    continue
                for other_cw in track["clips"]:
                    if other_cw is cw:
                        continue
                    try:
                        if not other_cw._alive: continue
                    except (RuntimeError, AttributeError): continue
                    if other_cw.clip_data.get("style_locked", False):
                        continue
                    other_cw.clip_data["subtitle_style"] = dict(default_style)
                    if "style_locked" in other_cw.clip_data:
                        del other_cw.clip_data["style_locked"]
                    other_cw.update()
                    count += 1
            rcount = count + (0 if locked_flag else 1)
            print(f"Reset {rcount} subtitle clips to default (locked clips preserved)")
            self._notify_subtitle_changed()

        elif action == "apply_style_all":
            # Apply style to current clip
            new_text = data["text"]
            new_style = data["style"]
            cw.clip_data["subtitle_text"] = new_text
            cw.clip_data["name"] = new_text[:30] + ("..." if len(new_text) > 30 else "")
            cw.clip_data["subtitle_style"] = new_style
            cw.update()
            # Apply style to ALL subtitle clips on ALL subtitle tracks
            count = 0
            for track in self.tracks:
                if track.get("type") != "subtitle":
                    continue
                for other_cw in track["clips"]:
                    if other_cw is cw:
                        continue
                    try:
                        if not other_cw._alive: continue
                    except (RuntimeError, AttributeError): continue
                    other_cw.clip_data["subtitle_style"] = dict(new_style)
                    other_cw.update()
                    count += 1
            from loguru import logger
            logger.info(f"Applied style to {count + 1} subtitle clips (all)")
            self._notify_subtitle_changed()
        elif action == "split":
            self._split_subtitle_clip(cw, data)
        elif action == "merge":
            self._merge_subtitle_clip(cw)

    def _split_subtitle_clip(self, cw, data=None):
        text = cw.clip_data.get("subtitle_text", "")
        if not text:
            return
        start = cw.clip_data.get("timeline_start", 0)
        dur = cw.clip_data.get("duration", 0)
        if dur < 0.2:
            return
        track_idx = -1
        for i, track in enumerate(self.tracks):
            if cw in track["clips"]:
                track_idx = i; break
        if track_idx < 0:
            return
        if data and data.get("text_before") and data.get("text_after"):
            t1 = data["text_before"]
            t2 = data["text_after"]
            ratio = data.get("ratio", 0.5)
            style = data.get("style", {})
        else:
            words = text.split()
            if len(words) >= 2:
                mid = len(words) // 2
                t1, t2 = " ".join(words[:mid]), " ".join(words[mid:])
            else:
                mc = len(text) // 2
                t1, t2 = text[:mc].strip(), text[mc:].strip()
            ratio = 0.5
            style = dict(cw.clip_data.get("subtitle_style", {}))
        if not t1:
            t1 = t2[:len(t2)//2]; t2 = t2[len(t2)//2:]
        dur1 = dur * ratio
        dur2 = dur - dur1
        in_pt = cw.clip_data.get("in_point", 0)
        path = cw.clip_data.get("path", "")
        old_data = dict(cw.clip_data)
        c1d = {"name": t1[:30], "path": path, "timeline_start": start,
               "duration": dur1, "in_point": in_pt, "out_point": in_pt + dur1,
               "source_duration": dur1, "track": track_idx,
               "subtitle_text": t1, "subtitle_style": dict(style)}
        c2d = {"name": t2[:30], "path": path, "timeline_start": start + dur1,
               "duration": dur2, "in_point": in_pt + dur1, "out_point": in_pt + dur,
               "source_duration": dur2, "track": track_idx,
               "subtitle_text": t2, "subtitle_style": dict(style)}
        self._safe_deselect()
        self.remove_clip_widget(cw)
        cw1 = self.add_clip(track_idx, c1d)
        cw2 = self.add_clip(track_idx, c2d)
        self._notify_subtitle_changed()
        logger.info(f"Subtitle split: '{t1[:20]}' + '{t2[:20]}'")
        if self._undo_manager:
            ti, cv = track_idx, self
            _od, _d1, _d2 = dict(old_data), dict(c1d), dict(c2d)
            _id1 = cw1._clip_id if cw1 else -1
            _id2 = cw2._clip_id if cw2 else -1
            def undo_split():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        if getattr(c, '_clip_id', -1) in (_id1, _id2):
                            cv.remove_clip_widget(c)
                cv.add_clip(ti, _od)
                cv._notify_subtitle_changed()
            def redo_split():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        cd = c.clip_data
                        if (cd.get("timeline_start") == _od.get("timeline_start")
                            and cd.get("subtitle_text") == _od.get("subtitle_text")):
                            cv.remove_clip_widget(c)
                            break
                cv.add_clip(ti, _d1)
                cv.add_clip(ti, _d2)
                cv._notify_subtitle_changed()
            self._undo_manager.push("Split subtitle", undo_split, redo_split)

    def _merge_subtitle_clip(self, cw):
        track_idx = -1
        for i, track in enumerate(self.tracks):
            if cw in track["clips"]:
                track_idx = i; break
        if track_idx < 0: return
        track = self.tracks[track_idx]
        cw_start = cw.clip_data.get("timeline_start", 0)
        next_cw = None
        min_start = float("inf")
        for other in track["clips"]:
            if other is cw or not other._alive: continue
            os = other.clip_data.get("timeline_start", 0)
            if os > cw_start and os < min_start:
                min_start = os; next_cw = other
        if next_cw is None:
            logger.warning("No next subtitle clip to merge"); return
        t1 = cw.clip_data.get("subtitle_text", cw.clip_data.get("name", ""))
        t2 = next_cw.clip_data.get("subtitle_text", next_cw.clip_data.get("name", ""))
        merged_text = f"{t1} {t2}".strip()
        next_end = next_cw.clip_data.get("timeline_start", 0) + next_cw.clip_data.get("duration", 0)
        new_dur = next_end - cw_start
        o1, o2 = dict(cw.clip_data), dict(next_cw.clip_data)
        id1 = getattr(cw, '_clip_id', -1)
        id2 = getattr(next_cw, '_clip_id', -1)
        md = {"name": merged_text[:30], "path": cw.clip_data.get("path", ""),
              "timeline_start": cw_start, "duration": new_dur,
              "in_point": cw.clip_data.get("in_point", 0),
              "out_point": cw.clip_data.get("in_point", 0) + new_dur,
              "source_duration": new_dur, "track": track_idx,
              "subtitle_text": merged_text}
        self._safe_deselect()
        self.remove_clip_widget(cw)
        self.remove_clip_widget(next_cw)
        mcw = self.add_clip(track_idx, md)
        self._notify_subtitle_changed()
        if self._undo_manager:
            ti, cv = track_idx, self
            mid = mcw._clip_id if mcw else -1
            d1, d2, dm = dict(o1), dict(o2), dict(md)
            def undo_mg():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        if getattr(c, '_clip_id', -1) == mid:
                            cv.remove_clip_widget(c)
                r1 = cv.add_clip(ti, d1); r2 = cv.add_clip(ti, d2)
                if r1: r1._clip_id = id1
                if r2: r2._clip_id = id2
                cv._notify_subtitle_changed(); cv.update()
            def redo_mg():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        if getattr(c, '_clip_id', -1) in (id1, id2):
                            cv.remove_clip_widget(c)
                r = cv.add_clip(ti, dm)
                if r: r._clip_id = mid
                cv._notify_subtitle_changed(); cv.update()
            self._undo_manager.push("Merge Subtitles", undo_mg, redo_mg)
        logger.info(f"Merged: '{t1[:15]}' + '{t2[:15]}'")

    def _notify_subtitle_changed(self):
        from PyQt6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, '_refresh_subtitle_overlay'):
                w._refresh_subtitle_overlay()
                return

    def _show_track_menu(self, track_idx, global_pos):
        track = self.tracks[track_idx]
        menu = QMenu(self)
        enabled = track.get("enabled", True)
        act_enable = menu.addAction("Disable Track" if enabled else "Enable Track")
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
        for i, track in enumerate(self.tracks):
            th = track.get("height", TRACK_HEIGHT_DEFAULT)
            ty = self._track_y(i)
            for cw in track["clips"]:
                if cw._alive:
                    cw.setMinimumHeight(th - 4)
                    cw.setMaximumHeight(th - 4)
                    cw.resize(cw.width(), th - 4)
                    cw.move(cw.x(), ty + 2)
                    cw.clip_data["track"] = i
                    cw.update()

    def _request_thumbnails(self, cw):
        if getattr(cw, '_filmstrip_requested', False):
            return
        cd = cw.clip_data
        path = cd.get('path', '')
        if not path or not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.png','.jpg','.jpeg','.bmp','.gif','.tiff','.tif','.webp','.svg'):
            from PyQt6.QtGui import QPixmap
            pm = QPixmap(path)
            if not pm.isNull():
                cw.set_filmstrip(pm, 1)
            cw._filmstrip_requested = True
            return
        duration = cd.get('duration', 0)
        in_pt = cd.get('in_point', 0)
        out_pt = cd.get('out_point', duration)
        clip_dur = out_pt - in_pt
        if clip_dur <= 0:
            clip_dur = duration
        if clip_dur <= 0:
            return
        track_h = cw.height()
        frame_h = max(28, track_h - 4)
        dar = 16 / 9
        frame_w = int(frame_h * dar)
        clip_px_w = max(10, int(clip_dur * getattr(self, 'pps', PIXELS_PER_SECOND)))
        num_frames = max(2, min(60, clip_px_w // max(1, frame_w)))
        ffmpeg = getattr(self, '_ffmpeg_path', 'ffmpeg')
        clip_id = getattr(cw, "_clip_id", -1)
        logger.info(f'Filmstrip request: {os.path.basename(path)} frames={num_frames} h={frame_h} ffmpeg={ffmpeg}')
        worker = FilmstripWorkerThread(clip_id, path, clip_dur, num_frames, frame_h, ffmpeg)
        worker.filmstrip_ready.connect(self._on_filmstrip_ready)
        if not hasattr(self, '_filmstrip_workers'):
            self._filmstrip_workers = []
        self._filmstrip_workers.append(worker)
        worker.start()
        cw._filmstrip_requested = True

    def _on_filmstrip_ready(self, clip_id, sprite_path, num_frames):
        from PyQt6.QtGui import QPixmap
        pm = QPixmap(sprite_path)
        if pm.isNull():
            logger.warning(f'Filmstrip load failed: {sprite_path}')
            return
        for track in self.tracks:
            for cw in track.get('clips', []):
                try:
                    if getattr(cw, "_clip_id", -1) == clip_id and cw.isVisible():
                        cw.set_filmstrip(pm, num_frames)
                        logger.info(f'Filmstrip loaded: {os.path.basename(cw.clip_data.get("path",""))} frames={num_frames}')
                        return
                except RuntimeError:
                    pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-aivideo-asset') or event.mimeData().hasText():
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
        track_idx, _ = self._track_at_y(int(y))
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
        h = RULER_HEIGHT + ZONE_BAR_HEIGHT + self._total_tracks_height() + 20
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
            th = track.get("height", TRACK_HEIGHT)
            y = self._track_y(i)
            enabled = track.get("enabled", True)
            color = CLR_TRACK if i % 2 == 0 else CLR_TRACK_ALT
            if not enabled:
                color = CLR_TRACK_DISABLED
            p.fillRect(0, y, w, th, color)
            if not enabled:
                p.fillRect(HEADER_WIDTH, y, w - HEADER_WIDTH, th, CLR_DISABLED_OVERLAY)
            eye = "O" if enabled else "X"
            p.setFont(_qf("Segoe UI", 12))
            p.setPen(QColor(200, 200, 200) if enabled else QColor(100, 60, 60))
            p.drawText(QRect(2, y, 18, th), Qt.AlignmentFlag.AlignCenter, eye)
            p.setPen(CLR_RULER_TEXT if enabled else QColor(100, 100, 100))
            p.setFont(_qf("Segoe UI", 11, QFont.Weight.Bold))
            icon = _TRACK_ICONS.get(track["type"], "?")
            flags = ""
            if track.get("mute"): flags += " M"
            if track.get("solo"): flags += " S"
            if track.get("lock"): flags += " L"
            if not enabled: flags += " OFF"
            label = f"{icon} {track['name']}{flags}"
            p.drawText(QRect(22, y, HEADER_WIDTH - 26, th),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(QColor(80, 80, 90), 2))
            p.drawLine(0, y + th - 1, w, y + th - 1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(120, 120, 130)))
            grip_y = y + th - 4
            for dx in (HEADER_WIDTH // 2 - 12, HEADER_WIDTH // 2, HEADER_WIDTH // 2 + 12):
                p.drawEllipse(QPoint(dx, grip_y), 2, 2)

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

        # Zone Bar (In/Out range)
        zone_y = RULER_HEIGHT
        zone_bar_rect = QRect(HEADER_WIDTH, zone_y, w - HEADER_WIDTH, ZONE_BAR_HEIGHT)
        p.fillRect(zone_bar_rect, QColor(50, 55, 65))
        if self._zone_enabled:
            zx_in = int(self._zone_in * self._pps) + HEADER_WIDTH
            z_out = self._zone_out if self._zone_out > 0 else self._total_duration
            zx_out = int(z_out * self._pps) + HEADER_WIDTH
            zone_sel = QRect(zx_in, zone_y, zx_out - zx_in, ZONE_BAR_HEIGHT)
            p.fillRect(zone_sel, CLR_ZONE_BAR)
            p.setPen(QPen(CLR_ZONE_BORDER, 1))
            p.drawRect(zone_sel)
            p.fillRect(QRect(zx_in - 5, zone_y, 10, ZONE_BAR_HEIGHT), CLR_ZONE_HANDLE)
            p.setPen(QColor(255, 255, 255))
            p.setFont(_qf("Segoe UI", 9))
            p.drawText(zx_in + 4, zone_y + 8, "I")
            p.fillRect(QRect(zx_out - 5, zone_y, 10, ZONE_BAR_HEIGHT), CLR_ZONE_HANDLE)
            p.drawText(zx_out - 10, zone_y + 8, "O")
        else:
            p.setPen(QColor(80, 80, 90))
            p.setFont(_qf("Segoe UI", 10))
            p.drawText(zone_bar_rect, Qt.AlignmentFlag.AlignCenter,
                       "Press I / O to set export range")

        # Snap lines
        p.setPen(QPen(CLR_SNAP, 1, Qt.PenStyle.DashLine))
        for sl in self._snap_lines:
            sx = int(sl * self._pps) + HEADER_WIDTH
            p.drawLine(sx, RULER_HEIGHT, sx, h)

        # Playhead
        px = int(self._playhead * self._pps) + HEADER_WIDTH
        track_bottom = RULER_HEIGHT + ZONE_BAR_HEIGHT + self._total_tracks_height()
        p.setPen(QPen(CLR_PLAYHEAD, 2))
        p.drawLine(px, 0, px, track_bottom)
        p.setBrush(QBrush(CLR_PLAYHEAD))
        p.setPen(Qt.PenStyle.NoPen)
        tri = [QPoint(px - 6, 0), QPoint(px + 6, 0), QPoint(px, 10)]
        p.drawPolygon(tri)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            pos = event.pos()
            # Zone handle detection
            if self._zone_enabled:
                if self._zone_in_handle_rect().adjusted(-6, 0, 6, 0).contains(pos):
                    self._dragging_zone_in = True
                    event.accept()
                    return
                if self._zone_out_handle_rect().adjusted(-6, 0, 6, 0).contains(pos):
                    self._dragging_zone_out = True
                    event.accept()
                    return
            # Zone bar click to create zone
            zbar = self._zone_bar_rect()
            if zbar.contains(pos) and not self._zone_enabled:
                t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
                self._zone_in = t
                self._zone_out = min(t + 1.0, self._total_duration)
                self._zone_enabled = True
                self._dragging_zone_out = True
                self.update()
                event.accept()
                return
            # Eye icon click
            if x < 20 and y >= RULER_HEIGHT + ZONE_BAR_HEIGHT:
                track_idx = self._track_at_y(y)[0]
                if 0 <= track_idx < len(self.tracks):
                    self.tracks[track_idx]["enabled"] = not self.tracks[track_idx].get("enabled", True)
                    self.update()
                    event.accept()
                    return
            # Resize drag on track separator
            if x < HEADER_WIDTH and y >= RULER_HEIGHT + ZONE_BAR_HEIGHT:
                sep_idx = self._near_track_separator(y)
                if sep_idx >= 0:
                    self._resizing_track = sep_idx
                    self._resize_start_y = y
                    self._resize_start_h = self.tracks[sep_idx].get("height", TRACK_HEIGHT)
                    self.setCursor(Qt.CursorShape.SplitVCursor)
                    event.accept()
                    return
            # Playhead click on ruler
            if y < RULER_HEIGHT and x >= HEADER_WIDTH:
                t = (x - HEADER_WIDTH) / self._pps
                self._playhead = max(0, t)
                self._dragging_playhead = True
                self.playhead_moved.emit(self._playhead)
                self.seek_requested.emit(self._playhead)
                self.update()
                event.accept()
                return
        if event.button() == Qt.MouseButton.RightButton:
            x, y = event.pos().x(), event.pos().y()
            if x < HEADER_WIDTH and y >= RULER_HEIGHT + ZONE_BAR_HEIGHT:
                track_idx = self._track_at_y(y)[0]
                if 0 <= track_idx < len(self.tracks):
                    self._show_track_menu(track_idx, event.globalPosition().toPoint())
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        pos = event.pos()
        # Zone handle dragging
        if self._dragging_zone_in:
            t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
            self._zone_in = min(t, self._zone_out - 0.1) if self._zone_out > 0 else t
            self.update()
            event.accept()
            return
        if self._dragging_zone_out:
            t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
            t = min(t, self._total_duration)
            self._zone_out = max(t, self._zone_in + 0.1)
            self.update()
            event.accept()
            return
        # Zone handle cursor
        if self._zone_enabled:
            if (self._zone_in_handle_rect().adjusted(-6, 0, 6, 0).contains(pos) or
                    self._zone_out_handle_rect().adjusted(-6, 0, 6, 0).contains(pos)):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self._zone_bar_rect().contains(pos):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Track resize drag
        if self._resizing_track >= 0:
            delta = y - self._resize_start_y
            new_h = max(TRACK_HEIGHT_MIN, min(TRACK_HEIGHT_MAX, self._resize_start_h + int(delta)))
            self.tracks[self._resizing_track]["height"] = new_h
            self._reposition_all_clips()
            self._update_size()
            self.update()
            event.accept()
            return
        # Playhead drag
        if self._dragging_playhead:
            t = max(0, (x - HEADER_WIDTH) / self._pps)
            self._playhead = t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
            return
        # Cursor near separator
        if x < HEADER_WIDTH and y >= RULER_HEIGHT + ZONE_BAR_HEIGHT:
            if self._near_track_separator(y) >= 0:
                self.setCursor(Qt.CursorShape.SplitVCursor)
            else:
                if self._tool != "razor":
                    self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            if self._tool == "razor":
                self.setCursor(Qt.CursorShape.SplitHCursor)
            elif self.cursor().shape() == Qt.CursorShape.SplitVCursor:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_zone_in or self._dragging_zone_out:
            self._dragging_zone_in = False
            self._dragging_zone_out = False
            if self._zone_out - self._zone_in < 0.1:
                self._zone_enabled = False
            self.update()
            event.accept()
            return
        if self._resizing_track >= 0:
            self._resizing_track = -1
            if self._tool != "razor":
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
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
            self.seek_requested.emit(-1.0)
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            frames = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            step = FRAME_DURATION * frames
            new_t = max(0, self._playhead - step)
            self._playhead = new_t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            frames = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            step = FRAME_DURATION * frames
            new_t = min(self._total_duration, self._playhead + step)
            self._playhead = new_t
            self.playhead_moved.emit(self._playhead)
            self.seek_requested.emit(self._playhead)
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Home:
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
        elif event.key() == Qt.Key.Key_I:
            self._zone_in = self._playhead
            if not self._zone_enabled:
                self._zone_out = self._total_duration
            if self._zone_out <= self._zone_in:
                self._zone_out = min(self._zone_in + 1.0, self._total_duration)
            self._zone_enabled = True
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_O:
            self._zone_out = self._playhead
            if not self._zone_enabled:
                self._zone_in = 0.0
            if self._zone_out <= self._zone_in:
                self._zone_in = max(self._zone_out - 1.0, 0.0)
            self._zone_enabled = True
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self._zone_enabled:
            self.clear_zone()
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
        if not hasattr(self, 'scroll') or not self.canvas:
            return
        px = int(self.canvas._playhead * self.canvas._pps) + HEADER_WIDTH
        scroll_bar = self.scroll.horizontalScrollBar()
        view_width = self.scroll.viewport().width()
        current_scroll = scroll_bar.value()
        margin = int(view_width * 0.15)
        if px > current_scroll + view_width - margin:
            new_scroll = px - view_width + margin + 50
            scroll_bar.setValue(min(new_scroll, scroll_bar.maximum()))
        elif px < current_scroll + margin:
            new_scroll = max(0, px - margin - 50)
            scroll_bar.setValue(new_scroll)

    def go_to_clip_start(self):
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