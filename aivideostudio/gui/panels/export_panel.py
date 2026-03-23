"""Export Panel - timeline-based export with FFmpeg + NVENC + audio mixing."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path as _Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import pyqtSignal, QObject
from loguru import logger


class ExportSignals(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


PRESETS = {
    "YouTube 1080p":        {"w": 1920, "h": 1080, "fps": 30, "vb": "8M",  "crf": "20"},
    "YouTube 1080p NVENC":  {"w": 1920, "h": 1080, "fps": 30, "vb": "8M",  "crf": "20", "gpu": True},
    "YouTube 4K":           {"w": 3840, "h": 2160, "fps": 30, "vb": "35M", "crf": "18"},
    "YouTube 4K NVENC":     {"w": 3840, "h": 2160, "fps": 30, "vb": "35M", "crf": "18", "gpu": True},
    "YouTube Shorts":       {"w": 1080, "h": 1920, "fps": 30, "vb": "6M",  "crf": "22"},
    "TikTok":               {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Instagram Reel":       {"w": 1080, "h": 1920, "fps": 30, "vb": "5M",  "crf": "23"},
    "Twitter/X":            {"w": 1280, "h": 720,  "fps": 30, "vb": "5M",  "crf": "22"},
    "Fast Preview":         {"w": 1280, "h": 720,  "fps": 30, "vb": "2M",  "crf": "28"},
    "Fast Preview NVENC":   {"w": 1280, "h": 720,  "fps": 30, "vb": "2M",  "crf": "28", "gpu": True},
    "Original Size":        {"w": 0,    "h": 0,    "fps": 0,  "vb": "10M", "crf": "20"},
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".svg"}
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


class ExportPanel(QWidget):
    def __init__(self, export_engine=None, parent=None):
        super().__init__(parent)
        self._engine = export_engine
        self._ffmpeg = "ffmpeg"
        if export_engine and hasattr(export_engine, "ffmpeg_path"):
            self._ffmpeg = str(export_engine.ffmpeg_path)
        self._video_path = None
        self._video_duration = 0.0
        self._subtitle_path = None
        self._process = None
        self._playback_engine = None
        self._timeline_canvas = None
        self._sig = ExportSignals()
        self._sig.progress.connect(self._on_progress)
        self._sig.status.connect(self._on_status)
        self._sig.finished.connect(self._on_finished)
        self._sig.error.connect(self._on_error)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # Preset
        preset_grp = QGroupBox("Export Settings")
        preset_lay = QVBoxLayout(preset_grp)

        row = QHBoxLayout()
        row.addWidget(QLabel("Preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(PRESETS.keys())
        idx = list(PRESETS.keys()).index("YouTube 1080p NVENC") if "YouTube 1080p NVENC" in PRESETS else 0
        self.combo_preset.setCurrentIndex(idx)
        row.addWidget(self.combo_preset)
        preset_lay.addLayout(row)

        # Export Range
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))
        self.combo_range = QComboBox()
        self.combo_range.addItems(["Full Timeline", "In-Out Range"])
        range_row.addWidget(self.combo_range)
        self.lbl_range_info = QLabel("")
        self.lbl_range_info.setStyleSheet("color: #88aaff; font-size: 11px;")
        range_row.addWidget(self.lbl_range_info)
        preset_lay.addLayout(range_row)

        # Options
        self.chk_burn = QCheckBox("Burn subtitles into video")
        self.chk_burn.setChecked(True)
        preset_lay.addWidget(self.chk_burn)

        self.chk_crop = QCheckBox("Crop for Shorts (9:16)")
        preset_lay.addWidget(self.chk_crop)

        self.chk_mix_audio = QCheckBox("Mix audio track (TTS, BGM)")
        self.chk_mix_audio.setChecked(True)
        preset_lay.addWidget(self.chk_mix_audio)

        lay.addWidget(preset_grp)

        # Info
        info_grp = QGroupBox("Source Info")
        info_lay = QVBoxLayout(info_grp)
        self.lbl_input = QLabel("Input: (none)")
        info_lay.addWidget(self.lbl_input)
        self.lbl_sub = QLabel("Subtitle: (none)")
        info_lay.addWidget(self.lbl_sub)
        self.lbl_dur = QLabel("")
        info_lay.addWidget(self.lbl_dur)
        lay.addWidget(info_grp)

        # Buttons
        row_btn = QHBoxLayout()
        self.btn_export = QPushButton("Export Timeline")
        self.btn_export.setStyleSheet(
            "QPushButton{background:#2979ff;color:white;padding:10px;font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:#448aff;}"
            "QPushButton:disabled{background:#666;}")
        self.btn_export.clicked.connect(self._on_export)
        row_btn.addWidget(self.btn_export)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(
            "QPushButton{background:#ff5252;color:white;padding:10px;font-size:14px;}")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        row_btn.addWidget(self.btn_cancel)
        lay.addLayout(row_btn)

        self.combo_range.currentIndexChanged.connect(lambda: self.update_range_info())

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)
        lay.addStretch()

    # External API
    def set_timeline_canvas(self, canvas):
        """Connect to timeline canvas for zone and track info."""
        self._timeline_canvas = canvas
        self._update_source_info()

    def _update_source_info(self):
        """Update Source Info from timeline tracks."""
        if not self._timeline_canvas:
            return
        tracks = self._timeline_canvas.tracks
        # Find first video track info
        for track in tracks:
            if track.get("type") == "video" and track.get("enabled", True):
                for clip in track.get("clips", []):
                    cw = clip if isinstance(clip, dict) else None
                    if cw is None and hasattr(clip, "clip_data"):
                        cw = clip.clip_data
                    if cw:
                        p = cw.get("path", "")
                        dur = cw.get("duration", 0)
                        if p:
                            self.lbl_input.setText("Input: " + _Path(p).name)
                            if dur > 0:
                                m, s = divmod(int(dur), 60)
                                self.lbl_dur.setText(f"Duration: {m:02d}:{s:02d}")
                            break
                break
        # Find subtitle
        for track in tracks:
            if track.get("type") == "subtitle" and track.get("enabled", True):
                for clip in track.get("clips", []):
                    cw = clip if isinstance(clip, dict) else None
                    if cw is None and hasattr(clip, "clip_data"):
                        cw = clip.clip_data
                    if cw:
                        p = cw.get("path", "")
                        if p and _Path(p).exists() and _Path(p).suffix.lower() in (".srt", ".ass", ".vtt"):
                            self._subtitle_path = str(p)
                            self.lbl_sub.setText("Subtitle: " + _Path(p).name)
                            break
                break

    def _get_export_range(self):
        """Return (start_sec, end_sec) or None for full timeline."""
        if self.combo_range.currentText() == "In-Out Range":
            if self._timeline_canvas:
                z_in, z_out, enabled = self._timeline_canvas.get_zone()
                if enabled and z_out > z_in:
                    return (z_in, z_out)
        return None

    def update_range_info(self):
        """Update the range info label from zone state."""
        if self._timeline_canvas:
            z_in, z_out, enabled = self._timeline_canvas.get_zone()
            if enabled and z_out > z_in:
                dur = z_out - z_in
                m_in, s_in = divmod(int(z_in), 60)
                m_out, s_out = divmod(int(z_out), 60)
                m_d, s_d = divmod(int(dur), 60)
                self.lbl_range_info.setText(
                    f"[{m_in}:{s_in:02d} \u2192 {m_out}:{s_out:02d}] ({m_d}:{s_d:02d})")
                return
        self.lbl_range_info.setText("")

    def set_playback_engine(self, engine):
        self._playback_engine = engine

    def set_input(self, path, duration=0.0):
        if path and _Path(path).exists():
            self._video_path = str(path)
            self._video_duration = duration
            self.lbl_input.setText("Input: " + _Path(path).name)
            if duration > 0:
                m, s = divmod(int(duration), 60)
                self.lbl_dur.setText(f"Duration: {m:02d}:{s:02d}")

    def set_subtitle(self, path):
        if path and _Path(path).exists():
            self._subtitle_path = str(path)
            self.lbl_sub.setText("Subtitle: " + _Path(path).name)

    # Export logic
    def _on_export(self):
        segments = self._get_video_segments()
        # Filter out invalid segments (duration=0, in_point beyond source)
        valid_segs = []
        for seg in segments:
            dur = seg["timeline_end"] - seg["timeline_start"]
            if dur < 0.01:
                logger.warning(f"Skipping zero-duration segment: {seg}")
                continue
            valid_segs.append(seg)
        segments = valid_segs
        logger.info(f"Video segments for export: {len(segments)}")
        for idx, seg in enumerate(segments):
            logger.info(f"  Seg {idx}: path={seg['path']} tl_start={seg['timeline_start']:.2f} tl_end={seg['timeline_end']:.2f} in_pt={seg.get('in_point',0):.2f}")
        if not segments:
            QMessageBox.warning(self, "Export Error",
                                "No clips on timeline.\nAdd clips to timeline first.")
            return

        # Apply export range filter
        export_range = self._get_export_range()
        if export_range:
            range_start, range_end = export_range
            filtered = []
            for seg in segments:
                s_start = seg["timeline_start"]
                s_end = seg["timeline_end"]
                if s_end <= range_start or s_start >= range_end:
                    continue
                new_seg = dict(seg)
                if s_start < range_start:
                    trim = range_start - s_start
                    new_seg["in_point"] = seg.get("in_point", 0) + trim
                    new_seg["timeline_start"] = range_start
                if s_end > range_end:
                    new_seg["timeline_end"] = range_end
                new_seg["timeline_start"] -= range_start
                new_seg["timeline_end"] -= range_start
                filtered.append(new_seg)
            segments = filtered
            if not segments:
                QMessageBox.warning(self, "Export Error",
                                    "No clips in the In-Out range.")
                return
            total_dur = max(s["timeline_end"] for s in segments)
        else:
            total_dur = max(s["timeline_end"] for s in segments)

        output, _ = QFileDialog.getSaveFileName(
            self, "Save Export", "timeline_export.mp4", "Video (*.mp4)")
        if not output:
            return

        preset_name = self.combo_preset.currentText()
        preset = PRESETS[preset_name]
        # Generate styled ASS from timeline subtitle events (matches preview)
        sub = None
        if self.chk_burn.isChecked():
            styled_ass = self._generate_styled_ass(export_range)
            if styled_ass:
                sub = styled_ass
                logger.info(f"Using styled ASS for export: {sub}")
            elif self._subtitle_path:
                sub = self._subtitle_path
                logger.info(f"Fallback to stored subtitle: {sub}")
        crop = self.chk_crop.isChecked()
        use_gpu = preset.get("gpu", False)
        mix_audio = self.chk_mix_audio.isChecked()

        audio_segments = []
        if mix_audio and self._playback_engine and hasattr(self._playback_engine, "get_ordered_audio_segments"):
            audio_segments = self._playback_engine.get_ordered_audio_segments()

        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Preparing...")

        t = threading.Thread(target=self._run_export, daemon=True,
                             args=(segments, audio_segments, output, preset,
                                   sub, crop, use_gpu, total_dur))
        t.start()

    def _get_video_segments(self):
        if self._playback_engine:
            return self._playback_engine.get_ordered_video_segments()
        return []

    def _on_cancel(self):
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def _get_vcodec(self, use_gpu, preset):
        vb = preset["vb"]
        crf = preset.get("crf", "20")
        if use_gpu:
            return ["h264_nvenc", "-preset", "p4", "-rc", "vbr",
                    "-cq", crf, "-b:v", vb, "-maxrate", vb]
        else:
            return ["libx264", "-preset", "medium", "-crf", crf, "-b:v", vb]

    def _run_export(self, video_segs, audio_segs, output, preset,
                    subtitle, crop, use_gpu, total_dur):
        tmpdir = tempfile.mkdtemp(prefix="avs_export_")
        try:
            pw, ph = preset["w"], preset["h"]
            fps = preset["fps"]
            vcodec = self._get_vcodec(use_gpu, preset)
            
            scale_vf = ""
            if pw > 0 and ph > 0:
                if crop and ph > pw:
                    scale_vf = f"scale=-2:{ph},crop={pw}:{ph}"
                else:
                    scale_vf = (f"scale={pw}:{ph}:force_original_aspect_ratio=decrease,"
                                f"pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2:black")
            
            # Log segments for debugging
            logger.info(f"Export: {len(video_segs)} video segments, {len(audio_segs)} audio segments")
            for si, seg in enumerate(video_segs):
                logger.info(f"  vSeg {si}: {seg['path']} tl={seg['timeline_start']:.2f}-{seg['timeline_end']:.2f} in_pt={seg.get('in_point',0):.2f}")
            
            # Step 1: Encode each video segment
            part_files = {}  # index → path
            num_segs = len(video_segs)
            for i, seg in enumerate(video_segs):
                pct = int(i / max(num_segs, 1) * 40)
                self._sig.status.emit(f"Encoding segment {i+1}/{num_segs}...")
                self._sig.progress.emit(pct)
                
                part_path = os.path.join(tmpdir, f"part_{i:04d}.mp4")
                path = seg["path"]
                ext = _Path(path).suffix.lower()
                is_image = ext in IMAGE_EXTS
                dur = seg["timeline_end"] - seg["timeline_start"]
                
                if dur < 0.01:
                    logger.warning(f"Skipping segment {i}: duration={dur:.3f}s")
                    continue
                
                if is_image:
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-loop", "1", "-framerate", str(fps or 30),
                           "-i", path, "-t", str(dur)]
                    vf_parts = [scale_vf] if scale_vf else []
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-pix_fmt", "yuv420p", "-an", part_path]
                else:
                    in_pt = seg.get("in_point", 0)
                    cmd = [self._ffmpeg, "-y", "-hide_banner",
                           "-ss", str(in_pt), "-i", path,
                           "-t", str(dur)]
                    vf_parts = [scale_vf] if scale_vf else []
                    if fps > 0:
                        vf_parts.append(f"fps={fps}")
                    if vf_parts:
                        cmd += ["-vf", ",".join(vf_parts)]
                    cmd += ["-c:v"] + list(vcodec)
                    cmd += ["-c:a", "aac", "-b:a", "192k",
                            "-pix_fmt", "yuv420p", part_path]
                
                logger.info(f"Segment {i}: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                _, stderr_bytes = self._process.communicate()
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                
                if self._process.returncode != 0:
                    logger.error(f"Segment {i} failed (rc={self._process.returncode}):\n{stderr}")
                    # Try CPU fallback if GPU encoding failed
                    if any(kw in stderr.lower() for kw in ["nvenc", "cuda", "gpu", "device", "hwaccel", "invalid argument"]):
                        logger.info(f"Segment {i}: Retrying with CPU encoder (libx264)...")
                        self._sig.status.emit(f"Segment {i+1} GPU failed, retrying CPU...")
                        cpu_cmd = []
                        skip_next = False
                        for ci, arg in enumerate(cmd):
                            if skip_next:
                                skip_next = False
                                continue
                            if arg in ("h264_nvenc", "hevc_nvenc"):
                                cpu_cmd.append("libx264")
                            elif arg in ("-preset", "-rc", "-cq", "-maxrate") and ci + 1 < len(cmd):
                                if arg == "-preset":
                                    cpu_cmd.append("-preset")
                                    cpu_cmd.append("medium")
                                    skip_next = True
                                elif arg in ("-rc", "-cq", "-maxrate"):
                                    skip_next = True  # skip GPU-only params
                                else:
                                    cpu_cmd.append(arg)
                            elif arg in ("vbr", "p4"):
                                continue  # skip GPU-only values
                            else:
                                cpu_cmd.append(arg)
                        # Replace -b:v with CRF for CPU
                        final_cmd = []
                        skip_next2 = False
                        for ci, arg in enumerate(cpu_cmd):
                            if skip_next2:
                                skip_next2 = False
                                continue
                            if arg == "-b:v" and ci + 1 < len(cpu_cmd):
                                final_cmd.extend(["-crf", "20"])
                                skip_next2 = True
                            else:
                                final_cmd.append(arg)
                        logger.info(f"CPU fallback: {' '.join(final_cmd)}")
                        self._process = subprocess.Popen(
                            final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=0x08000000)
                        _, stderr_bytes2 = self._process.communicate()
                        stderr2 = stderr_bytes2.decode("utf-8", errors="replace") if stderr_bytes2 else ""
                        if self._process.returncode != 0:
                            logger.error(f"CPU fallback also failed: {stderr2}")
                            continue
                    else:
                        continue  # non-GPU error, skip segment
                if _Path(part_path).exists():
                    part_files[i] = part_path
            
            if not part_files:
                self._sig.error.emit("No segments were created.")
                return
            
            # Step 2: Insert black gaps between segments
            final_parts = []
            exported_indices = sorted(part_files.keys())
            for pos, seg_i in enumerate(exported_indices):
                seg = video_segs[seg_i]
                gap_start = seg["timeline_start"]
                if pos == 0 and gap_start > 0.05:
                    gap_path = os.path.join(tmpdir, "gap_start.mp4")
                    self._make_black(gap_path, gap_start, pw or 1920, ph or 1080, fps or 30, vcodec)
                    if _Path(gap_path).exists():
                        logger.info(f"Gap added: {gap_path} exists={_Path(gap_path).exists()}")
                        final_parts.append(gap_path)
                elif pos > 0:
                    prev_seg_i = exported_indices[pos - 1]
                    prev_end = video_segs[prev_seg_i]["timeline_end"]
                    gap_dur = gap_start - prev_end
                    if gap_dur > 0.05:
                        gap_path = os.path.join(tmpdir, f"gap_{seg_i:04d}.mp4")
                        self._make_black(gap_path, gap_dur, pw or 1920, ph or 1080, fps or 30, vcodec)
                        if _Path(gap_path).exists():
                            final_parts.append(gap_path)
                final_parts.append(part_files[seg_i])
            
            # Step 3: Concat
            self._sig.status.emit("Concatenating video...")
            self._sig.progress.emit(50)
            
            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for fp in final_parts:
                    safe = fp.replace(chr(92), "/")
                    f.write(f"file '{safe}'\n")
            
            need_subtitle = subtitle and _Path(subtitle).exists()
            need_audio_mix = bool(audio_segs)
            concat_out = os.path.join(tmpdir, "concat_raw.mp4") if (need_subtitle or need_audio_mix) else output
            
            cmd = [self._ffmpeg, "-y", "-hide_banner",
                   "-f", "concat", "-safe", "0", "-i", concat_list,
                   "-c", "copy", concat_out]
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000)
            _, stderr_bytes = self._process.communicate()
            if self._process.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                self._sig.error.emit(f"Concat failed:\n{stderr[-300:]}")
                return
            
            current_video = concat_out
            
            # Step 4: Mix audio
            if need_audio_mix:
                self._sig.status.emit("Mixing audio tracks...")
                self._sig.progress.emit(65)
                mixed = os.path.join(tmpdir, "audio_mixed.mp4")
                ok = self._mix_audio(current_video, audio_segs, mixed, total_dur, vcodec)
                if ok and _Path(mixed).exists():
                    current_video = mixed
            
            # Step 5: Burn subtitles
            if need_subtitle:
                self._sig.status.emit("Burning subtitles...")
                self._sig.progress.emit(80)
                sub_out = output
                temp_sub = os.path.join(tempfile.gettempdir(),
                                        "avs_burn_sub" + _Path(subtitle).suffix)
                shutil.copy2(subtitle, temp_sub)
                safe_sub = temp_sub.replace(chr(92), "/").replace(":", "\\:")

                if temp_sub.lower().endswith(".ass"):
                    sub_vf = f"ass='{safe_sub}'"
                    logger.info("Burning ASS subtitle with full styles")
                else:
                    font_size = max(12, min(20, int(ph / 80))) if ph > 0 else 16
                    margin_v = max(10, int(ph / 40)) if ph > 0 else 20
                    sub_vf = (f"subtitles='{safe_sub}':"
                              f"force_style='FontName=Malgun Gothic,FontSize={font_size},"
                              f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                              f"Outline=2,Shadow=1,MarginV={margin_v}'")

                cmd = [self._ffmpeg, "-y", "-hide_banner",
                       "-i", current_video, "-vf", sub_vf,
                       "-c:v"] + list(vcodec) + [
                       "-c:a", "copy", sub_out]
                logger.info(f"Subtitle burn: {' '.join(cmd)}")
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=0x08000000)
                _, stderr_bytes = self._process.communicate()
                if self._process.returncode != 0:
                    stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                    logger.error(f"Subtitle burn failed: {stderr[-500:]}")
                    if current_video != output:
                        shutil.copy2(current_video, output)
                else:
                    current_video = sub_out
                if os.path.exists(temp_sub):
                    os.remove(temp_sub)
            elif current_video != output:
                shutil.copy2(current_video, output)
            
            # Done
            self._sig.progress.emit(100)
            if _Path(output).exists():
                mb = _Path(output).stat().st_size / (1024 * 1024)
                self._sig.finished.emit(
                    f"Export complete!\n{_Path(output).name} ({mb:.1f} MB)\n"
                    f"Encoder: {'NVENC GPU' if preset.get('gpu') else 'CPU (x264)'}")
            else:
                self._sig.error.emit("Output file was not created.")
            
        except Exception as e:
            logger.exception("Export failed")
            self._sig.error.emit(str(e))
        finally:
            self._process = None
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _mix_audio(self, video_path, audio_segs, output, total_dur, vcodec):
        if not audio_segs:
            return False
        tmpdir = os.path.dirname(output)
        inputs = ["-i", video_path]
        filter_parts = []
        audio_labels = []
        filter_parts.append("[0:a]aresample=44100[orig]")
        audio_labels.append("[orig]")
        for i, seg in enumerate(audio_segs):
            inp_idx = i + 1
            inputs += ["-i", seg["path"]]
            delay_ms = int(seg["timeline_start"] * 1000)
            in_pt = seg.get("in_point", 0)
            dur = seg["timeline_end"] - seg["timeline_start"]
            label = f"[a{i}]"
            f = (f"[{inp_idx}:a]atrim=start={in_pt}:duration={dur},"
                 f"asetpts=PTS-STARTPTS,"
                 f"adelay={delay_ms}|{delay_ms},"
                 f"aresample=44100{label}")
            filter_parts.append(f)
            audio_labels.append(label)
        n = len(audio_labels)
        mix_inputs = "".join(audio_labels)
        filter_parts.append(f"{mix_inputs}amix=inputs={n}:duration=longest:dropout_transition=0[aout]")
        filter_complex = ";".join(filter_parts)
        cmd = [self._ffmpeg, "-y", "-hide_banner"] + inputs
        cmd += ["-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", output]
        logger.info(f"Audio mix: {len(audio_segs)} audio clips")
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x08000000)
            _, stderr_bytes = self._process.communicate()
            if self._process.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                logger.warning(f"Audio mix failed (non-fatal): {stderr[-300:]}")
                shutil.copy2(video_path, output)
                return True
        except Exception as e:
            logger.warning(f"Audio mix error: {e}")
            shutil.copy2(video_path, output)
        return True

    def _generate_styled_ass(self, export_range=None):
        """Generate ASS subtitle file from timeline events with full styles.
        Matches preview rendering exactly."""
        if not self._timeline_canvas:
            return None
        events = []
        for track in self._timeline_canvas.tracks:
            if track.get("type") != "subtitle" or not track.get("enabled", True):
                continue
            for clip in track.get("clips", []):
                try:
                    if not clip._alive: continue
                except (RuntimeError, AttributeError): continue
                cd = clip.clip_data
                events.append({
                    "start": cd.get("timeline_start", 0),
                    "end": cd.get("timeline_start", 0) + cd.get("duration", 0),
                    "text": cd.get("subtitle_text", cd.get("name", "")),
                    "style": cd.get("subtitle_style", {}),
                })
        if not events:
            return None
        events.sort(key=lambda e: e["start"])
        # Apply export range offset
        if export_range:
            r_start, r_end = export_range
            filtered = []
            for ev in events:
                if ev["end"] <= r_start or ev["start"] >= r_end:
                    continue
                new_ev = dict(ev)
                new_ev["start"] = max(0, ev["start"] - r_start)
                new_ev["end"] = min(r_end - r_start, ev["end"] - r_start)
                filtered.append(new_ev)
            events = filtered
        if not events:
            return None

        def fmt_time(sec):
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = sec % 60
            return f"{h}:{m:02d}:{s:05.2f}"

        ass_lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "WrapStyle: 0",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, Strikeout, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Malgun Gothic,22,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,30,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        for ev in events:
            text = ev["text"].replace("\n", "\\N")
            style = ev.get("style", {})
            tags = []
            if style.get("font"):
                tags.append(f"\\fn{style['font']}")
            if style.get("size"):
                tags.append(f"\\fs{style['size']}")
            if style.get("bold"):
                tags.append("\\b1")
            if style.get("italic"):
                tags.append("\\i1")
            if style.get("font_color"):
                c = style["font_color"].lstrip("#")
                if len(c) == 6:
                    tags.append(f"\\c&H{c[4:6]}{c[2:4]}{c[0:2]}&")
            if style.get("outline_color"):
                c = style["outline_color"].lstrip("#")
                if len(c) == 6:
                    tags.append(f"\\3c&H{c[4:6]}{c[2:4]}{c[0:2]}&")
            if style.get("outline_size") is not None:
                tags.append(f"\\bord{style['outline_size']}")
            if style.get("shadow") is False:
                tags.append("\\shad0")
            if style.get("bg_box"):
                tags.append("\\3a&H80&")
            if style.get("alignment"):
                tags.append(f"\\an{style['alignment']}")
            anim_tag = style.get("animation_tag", "")
            if anim_tag:
                tags.append(anim_tag)
            tag_str = "{" + "".join(tags) + "}" if tags else ""
            s_time = fmt_time(ev["start"])
            e_time = fmt_time(ev["end"])
            ass_lines.append(f"Dialogue: 0,{s_time},{e_time},Default,,0,0,0,,{tag_str}{text}")

        import tempfile
        ass_path = os.path.join(tempfile.gettempdir(), "avs_export_styled.ass")
        with open(ass_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(ass_lines))
        logger.info(f"Generated styled ASS: {ass_path} ({len(events)} events)")
        return ass_path

    def _make_black(self, out_path, duration, w, h, fps, vcodec):
        """Generate a black video segment. Always uses CPU encoder for reliability."""
        cmd = [self._ffmpeg, "-y", "-hide_banner",
               "-f", "lavfi", "-i",
               f"color=c=black:s={w}x{h}:r={fps}:d={duration}",
               "-f", "lavfi", "-i",
               f"anullsrc=r=44100:cl=stereo",
               "-t", str(duration),
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
               "-c:a", "aac", "-b:a", "128k",
               "-pix_fmt", "yuv420p",
               "-shortest",
               out_path]
        logger.info(f"Black gap: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x08000000)
        _, stderr_bytes = proc.communicate()
        if proc.returncode != 0:
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            logger.error(f"Black gap failed: {stderr}")

    def _on_progress(self, v):
        self.progress.setValue(v)

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setValue(100)
        self.lbl_status.setText(msg.split("\n")[0])
        QMessageBox.information(self, "Export Complete", msg)

    def _on_error(self, msg):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.lbl_status.setText("Error: " + msg[:100])
        QMessageBox.critical(self, "Export Error", msg[:500])
        logger.error("Export error: " + msg)