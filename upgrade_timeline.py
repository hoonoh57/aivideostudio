"""upgrade_timeline.py — 멀티트랙 + 자동배치 + 뮤트/솔로/잠금 + 트랙 추가/삭제"""
import os

BASE = r"D:\aivideostudio\aivideostudio"

# ============================================================
# 1) timeline_panel.py — 멀티트랙 업그레이드
# ============================================================
tp_path = os.path.join(BASE, "gui", "panels", "timeline_panel.py")

# 파일이 너무 크므로 핵심 부분만 수정: main_window.py의 기본 트랙 생성 부분
# timeline_panel.py 자체는 이미 멀티트랙을 지원하는 구조이므로
# 트랙 추가/삭제 UI와 뮤트/솔로 기능을 추가합니다

with open(tp_path, "r", encoding="utf-8") as f:
    tp_code = f.read()

changes = 0

# 1-1) 트랙 헤더에 뮤트/솔로 버튼 추가 (TrackData에 mute/solo/lock 속성)
old_add_track = '''    def add_track(self, name, track_type="video"):
        track = {"name": name, "type": track_type, "clips": []}
        self.tracks.append(track)
        self._update_size()
        self.update()
        logger.info("Track added: " + name)
        return track'''

new_add_track = '''    def add_track(self, name, track_type="video"):
        track = {
            "name": name, "type": track_type, "clips": [],
            "mute": False, "solo": False, "lock": False, "visible": True,
        }
        self.tracks.append(track)
        self._update_size()
        self.update()
        logger.info("Track added: " + name + " (" + track_type + ")")
        return track'''

if old_add_track in tp_code:
    tp_code = tp_code.replace(old_add_track, new_add_track)
    changes += 1

# 1-2) 트랙 헤더 그리기에 뮤트/솔로/잠금 표시 추가
old_paint_header = '''            p.drawText(QRect(4, y, HEADER_WIDTH - 8, TRACK_HEIGHT),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       track["name"])'''

new_paint_header = '''            # Track name + type icon
            icon = "V" if track["type"] == "video" else "A"
            mute_txt = " [M]" if track.get("mute") else ""
            solo_txt = " [S]" if track.get("solo") else ""
            lock_txt = " [L]" if track.get("lock") else ""
            label = icon + " " + track["name"] + mute_txt + solo_txt + lock_txt
            p.drawText(QRect(4, y, HEADER_WIDTH - 8, TRACK_HEIGHT),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)'''

if old_paint_header in tp_code:
    tp_code = tp_code.replace(old_paint_header, new_paint_header)
    changes += 1

# 1-3) 트랙 헤더 우클릭 메뉴 (뮤트/솔로/잠금/삭제)
old_mouse_press = '''    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()
            y = event.pos().y()
            if y < RULER_HEIGHT and x > HEADER_WIDTH:'''

new_mouse_press = '''    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            x = event.pos().x()
            y = event.pos().y()
            if x < HEADER_WIDTH and y >= RULER_HEIGHT:
                track_idx = (y - RULER_HEIGHT) // TRACK_HEIGHT
                if 0 <= track_idx < len(self.tracks):
                    self._show_track_menu(track_idx, event.globalPosition().toPoint())
                    event.accept()
                    return
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()
            y = event.pos().y()
            if y < RULER_HEIGHT and x > HEADER_WIDTH:'''

if old_mouse_press in tp_code:
    tp_code = tp_code.replace(old_mouse_press, new_mouse_press)
    changes += 1

# 1-4) 트랙 메뉴 메서드 추가 (paintEvent 바로 앞에)
track_menu_method = '''
    def _show_track_menu(self, track_idx, pos):
        """Right-click menu on track header."""
        from PyQt6.QtWidgets import QMenu
        track = self.tracks[track_idx]
        menu = QMenu(self)
        
        act_mute = menu.addAction("Unmute" if track.get("mute") else "Mute")
        act_solo = menu.addAction("Unsolo" if track.get("solo") else "Solo")
        act_lock = menu.addAction("Unlock" if track.get("lock") else "Lock")
        menu.addSeparator()
        act_add_video = menu.addAction("+ Add Video Track")
        act_add_audio = menu.addAction("+ Add Audio Track")
        menu.addSeparator()
        act_delete = menu.addAction("Delete Track")
        act_delete.setEnabled(len(self.tracks) > 1)
        
        action = menu.exec(pos)
        if action == act_mute:
            track["mute"] = not track.get("mute", False)
            self.update()
        elif action == act_solo:
            track["solo"] = not track.get("solo", False)
            self.update()
        elif action == act_lock:
            track["lock"] = not track.get("lock", False)
            self.update()
        elif action == act_add_video:
            n = sum(1 for t in self.tracks if t["type"] == "video") + 1
            self.add_track(f"Video {n}", "video")
        elif action == act_add_audio:
            n = sum(1 for t in self.tracks if t["type"] == "audio") + 1
            self.add_track(f"Audio {n}", "audio")
        elif action == act_delete:
            if len(self.tracks) > 1:
                # Remove all clips in track
                for cw in list(track["clips"]):
                    self.remove_clip_widget(cw)
                self.tracks.remove(track)
                # Reposition remaining clips
                for i, t in enumerate(self.tracks):
                    for cw in t["clips"]:
                        if cw._alive:
                            cw.move(cw.x(), RULER_HEIGHT + i * TRACK_HEIGHT + 2)
                self._update_size()
                self.update()

'''

# Insert before paintEvent
if "_show_track_menu" not in tp_code:
    tp_code = tp_code.replace(
        "    def paintEvent(self, event):",
        track_menu_method + "    def paintEvent(self, event):"
    )
    changes += 1

# 1-5) 잠긴 트랙에서 클립 드래그 방지
old_clip_click = '''    def _on_clip_clicked(self, cw, event):
        if not cw._alive:
            return
        if self._tool == "razor":'''

new_clip_click = '''    def _on_clip_clicked(self, cw, event):
        if not cw._alive:
            return
        # Check if track is locked
        for track in self.tracks:
            if cw in track["clips"] and track.get("lock"):
                return  # locked track, ignore
        if self._tool == "razor":'''

if old_clip_click in tp_code:
    tp_code = tp_code.replace(old_clip_click, new_clip_click)
    changes += 1

with open(tp_path, "w", encoding="utf-8") as f:
    f.write(tp_code)
print(f"[1] OK: {tp_path} — {changes} changes applied")


# ============================================================
# 2) main_window.py — 기본 트랙 확장 + 자동 배치
# ============================================================
mw_path = os.path.join(BASE, "gui", "main_window.py")
with open(mw_path, "r", encoding="utf-8") as f:
    mw_code = f.read()

mw_changes = 0

# 2-1) 기본 트랙을 4개로 확장: V1, V2, A1, A2
old_default_tracks = '''        self.timeline_panel.add_track("Video 1", "video")
        self.timeline_panel.add_track("Audio 1", "audio")'''

new_default_tracks = '''        self.timeline_panel.add_track("Video 1", "video")
        self.timeline_panel.add_track("Video 2", "video")
        self.timeline_panel.add_track("Audio 1", "audio")
        self.timeline_panel.add_track("Audio 2", "audio")'''

if old_default_tracks in mw_code:
    mw_code = mw_code.replace(old_default_tracks, new_default_tracks)
    mw_changes += 1

# 2-2) 더블클릭 시 파일 타입에 따라 자동 트랙 배치
old_add_to_timeline = '''    def add_asset_to_timeline(self, file_path):
        """Double-click in media panel: add asset to timeline at end of track 0."""
        # Find the asset
        asset = None
        for a in self.project.assets:
            if a.path == file_path:
                asset = a
                break
        if asset is None:
            # Not yet imported  import first
            self._on_file_imported(file_path)
            for a in self.project.assets:
                if a.path == file_path:
                    asset = a
                    break
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return

        duration = asset.duration if asset.duration > 0 else 5.0

        # Find end of existing clips on track 0
        end_time = 0.0
        if self.timeline_panel.canvas.tracks:
            for cw in self.timeline_panel.canvas.tracks[0]["clips"]:
                try:
                    if cw._alive:
                        cend = cw.clip_data.get("timeline_start", 0) + cw.clip_data.get("duration", 0)
                        end_time = max(end_time, cend)
                except (RuntimeError, AttributeError):
                    continue

        clip = Clip(asset_path=file_path, track_index=0,
                    source_in=0.0, source_out=duration, name=asset.name)
        self.project.add_clip(clip)

        clip_dict = {
            "name": asset.name,
            "path": file_path,
            "timeline_start": end_time,
            "duration": duration,
            "in_point": 0.0,
            "out_point": duration,
            "source_duration": duration,
            "track": 0,
        }
        self.timeline_panel.add_clip(0, clip_dict)
        self._sync_timeline_to_preview()
        self.preview.seek_to(end_time)
        self.status_bar.showMessage(
            f"Added to timeline: {asset.name} at {end_time:.1f}s", 3000)'''

new_add_to_timeline = '''    def _find_track_index(self, track_type):
        """Find the first track of given type, or create one."""
        for i, t in enumerate(self.timeline_panel.canvas.tracks):
            if t["type"] == track_type:
                return i
        # Create new track
        n = len(self.timeline_panel.canvas.tracks)
        name = f"Video {n+1}" if track_type == "video" else f"Audio {n+1}"
        self.timeline_panel.add_track(name, track_type)
        return len(self.timeline_panel.canvas.tracks) - 1

    def _find_track_end(self, track_index):
        """Find the end time of the last clip on a track."""
        end_time = 0.0
        if track_index < len(self.timeline_panel.canvas.tracks):
            for cw in self.timeline_panel.canvas.tracks[track_index]["clips"]:
                try:
                    if cw._alive:
                        cend = cw.clip_data.get("timeline_start", 0) + cw.clip_data.get("duration", 0)
                        end_time = max(end_time, cend)
                except (RuntimeError, AttributeError):
                    continue
        return end_time

    AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".svg"}

    def add_asset_to_timeline(self, file_path):
        """Double-click in media panel: auto-place on correct track type."""
        asset = None
        for a in self.project.assets:
            if a.path == file_path:
                asset = a
                break
        if asset is None:
            self._on_file_imported(file_path)
            for a in self.project.assets:
                if a.path == file_path:
                    asset = a
                    break
        if asset is None:
            self.status_bar.showMessage(f"Cannot add: {Path(file_path).name}", 5000)
            return

        duration = asset.duration if asset.duration > 0 else 5.0
        ext = Path(file_path).suffix.lower()

        # Auto-detect track type
        if ext in self.AUDIO_EXTS or (asset.has_audio and not asset.has_video):
            track_type = "audio"
        else:
            track_type = "video"  # video and images go to video track

        track_idx = self._find_track_index(track_type)
        end_time = self._find_track_end(track_idx)

        clip = Clip(asset_path=file_path, track_index=track_idx,
                    source_in=0.0, source_out=duration, name=asset.name)
        self.project.add_clip(clip)

        clip_dict = {
            "name": asset.name,
            "path": file_path,
            "timeline_start": end_time,
            "duration": duration,
            "in_point": 0.0,
            "out_point": duration,
            "source_duration": duration,
            "track": track_idx,
        }
        self.timeline_panel.add_clip(track_idx, clip_dict)
        self._sync_timeline_to_preview()
        self.preview.seek_to(end_time)
        track_name = self.timeline_panel.canvas.tracks[track_idx]["name"]
        self.status_bar.showMessage(
            f"Added to {track_name}: {asset.name} at {end_time:.1f}s", 3000)'''

if old_add_to_timeline in mw_code:
    mw_code = mw_code.replace(old_add_to_timeline, new_add_to_timeline)
    mw_changes += 1
else:
    print(f"[2] WARN: add_asset_to_timeline pattern not found")

with open(mw_path, "w", encoding="utf-8") as f:
    f.write(mw_code)
print(f"[2] OK: {mw_path} — {mw_changes} changes applied")


# ============================================================
print()
print("=" * 60)
print("Timeline upgrade complete!")
print()
print("  [1] timeline_panel.py:")
print("      - Track header: right-click -> Mute/Solo/Lock/Delete")
print("      - Track header: right-click -> Add Video/Audio Track")
print("      - Track type icon (V/A) in header")
print("      - Locked track: clips cannot be dragged")
print("      - Track properties: mute, solo, lock, visible")
print()
print("  [2] main_window.py:")
print("      - Default 4 tracks: V1, V2, A1, A2")
print("      - Auto-place: audio files -> Audio track")
print("      - Auto-place: video/images -> Video track")
print("      - Smart track end detection")
print()
print("Next: python -m aivideostudio.main")
print("=" * 60)
