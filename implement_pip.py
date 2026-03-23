
"""implement_pip.py — PIP(Picture-in-Picture) 기능 구현
V2 트랙 클립을 V1 위에 오버레이하여 Export.
Phase 1: Export PIP (FFmpeg overlay filter)
Phase 2: Preview PIP (mpv overlay) — 다음 단계
"""
import re
import py_compile
from pathlib import Path

BASE_CORE = Path(r"D:\aivideostudio\aivideostudio\core")
BASE_GUI = Path(r"D:\aivideostudio\aivideostudio\gui\panels")

changes = []

# ═══════════════════════════════════════════════════════════
# 1. playback_engine.py — 멀티 비디오 레이어 지원
# ═══════════════════════════════════════════════════════════
pe_path = BASE_CORE / "playback_engine.py"
pe = pe_path.read_text(encoding="utf-8")
pe_orig = pe

# 1a. query() — "video"를 단일 info → list로 변경 + video_layers 추가
old_query_init = '''        result = {
            "video": None,
            "audio": [],
            "subtitle": [],
            "timeline_pos": t,
            "is_gap": True,
            "video_muted": False,
        }'''
new_query_init = '''        result = {
            "video": None,
            "video_layers": [],  # PIP: all video layers (track_idx order)
            "audio": [],
            "subtitle": [],
            "timeline_pos": t,
            "is_gap": True,
            "video_muted": False,
        }'''
if old_query_init in pe:
    pe = pe.replace(old_query_init, new_query_init)
    changes.append("[FIX] playback_engine.py: query() — added video_layers list")

# 1b. query() — 비디오 트랙 처리 시 video_layers에 추가
old_video_block = '''                if track_type == "video":
                        result["video"] = info
                        if is_muted:
                            result["video_muted"] = True
                        result["is_gap"] = False'''
new_video_block = '''                if track_type == "video":
                        info["track_name"] = track.get("name", "")
                        info["track_idx"] = self._tracks.index(track)
                        result["video_layers"].append(info)
                        if result["video"] is None:
                            result["video"] = info
                        if is_muted:
                            result["video_muted"] = True
                        result["is_gap"] = False'''
if old_video_block in pe:
    pe = pe.replace(old_video_block, new_video_block)
    changes.append("[FIX] playback_engine.py: query() — collect video_layers for PIP")

# 1c. get_pip_segments() — PIP용 세그먼트 반환 (V1=base, V2+=overlay)
pip_method = '''
    def get_pip_video_layers(self):
        """Return video segments grouped by track for PIP compositing.
        Returns: list of (track_name, track_idx, [segments])
        Track 0 = base layer, Track 1+ = overlay layers.
        """
        layers = []
        for idx, track in enumerate(self._tracks):
            if track.get("type") != "video":
                continue
            if not track.get("enabled", True):
                continue
            segs = []
            for clip in track.get("clips", []):
                cs = clip.get("timeline_start", 0)
                dur = clip.get("duration", 0)
                segs.append({
                    "timeline_start": cs,
                    "timeline_end": cs + dur,
                    "path": clip.get("path", ""),
                    "in_point": clip.get("in_point", 0),
                    "out_point": clip.get("out_point", clip.get("in_point", 0) + dur),
                    "pip": clip.get("pip", {}),  # {x, y, w, h, opacity}
                })
            if segs:
                segs.sort(key=lambda s: s["timeline_start"])
                layers.append({
                    "track_name": track.get("name", f"Video {idx+1}"),
                    "track_idx": idx,
                    "segments": segs,
                })
        return layers
'''

# Insert before the last method or at end of class
if "def get_pip_video_layers" not in pe:
    # Find last method in class
    insert_pos = pe.rfind("\n    def get_ordered_subtitle_segments")
    if insert_pos > 0:
        pe = pe[:insert_pos] + pip_method + pe[insert_pos:]
        changes.append("[FIX] playback_engine.py: Added get_pip_video_layers() method")

if pe != pe_orig:
    pe_path.write_text(pe, encoding="utf-8")
    print(f"[SAVED] {pe_path}")

# ═══════════════════════════════════════════════════════════
# 2. export_panel.py — PIP overlay export
# ═══════════════════════════════════════════════════════════
ep_path = BASE_GUI / "export_panel.py"
ep = ep_path.read_text(encoding="utf-8")
ep_orig = ep

# 2a. _on_export() — PIP 레이어 수집
old_on_export_segments = '''    def _on_export(self):
        segments = self._get_video_segments()
        if not segments:
            QMessageBox.warning(self, "Export Error",
                                "No clips on timeline.\\nAdd clips to timeline first.")
            return
        total_dur = max(s["timeline_end"] for s in segments)'''
new_on_export_segments = '''    def _on_export(self):
        segments = self._get_video_segments()
        if not segments:
            QMessageBox.warning(self, "Export Error",
                                "No clips on timeline.\\nAdd clips to timeline first.")
            return
        total_dur = max(s["timeline_end"] for s in segments)

        # Collect PIP overlay layers (V2, V3, ...)
        pip_layers = []
        if self._playback_engine and hasattr(self._playback_engine, "get_pip_video_layers"):
            all_layers = self._playback_engine.get_pip_video_layers()
            if len(all_layers) > 1:
                pip_layers = all_layers[1:]  # skip base layer (V1)
                logger.info(f"PIP: {len(pip_layers)} overlay layer(s) detected")'''
if old_on_export_segments in ep:
    ep = ep.replace(old_on_export_segments, new_on_export_segments)
    changes.append("[FIX] export_panel.py: _on_export — collect PIP layers")

# 2b. Pass pip_layers to _run_export
old_thread_start = '''        t = threading.Thread(target=self._run_export, daemon=True,
                            args=(segments, audio_segments, output, preset,
                                  sub, crop, use_gpu, total_dur))'''
new_thread_start = '''        t = threading.Thread(target=self._run_export, daemon=True,
                            args=(segments, audio_segments, output, preset,
                                  sub, crop, use_gpu, total_dur, pip_layers))'''
if old_thread_start in ep:
    ep = ep.replace(old_thread_start, new_thread_start)
    changes.append("[FIX] export_panel.py: pass pip_layers to _run_export thread")

# 2c. _run_export signature — add pip_layers parameter
old_run_sig = "    def _run_export(self, video_segs, audio_segs, output, preset, subtitle, crop, use_gpu, total_dur):"
new_run_sig = "    def _run_export(self, video_segs, audio_segs, output, preset, subtitle, crop, use_gpu, total_dur, pip_layers=None):"
if old_run_sig in ep:
    ep = ep.replace(old_run_sig, new_run_sig)
    changes.append("[FIX] export_panel.py: _run_export — added pip_layers parameter")

# 2d. Add PIP overlay step after concat (Step 3.5)
# Find the line after concat step and before audio mix
old_after_concat = '''            current_video = concat_out

            # ── Step 4: Mix audio tracks ──'''
new_after_concat = '''            current_video = concat_out

            # ── Step 3.5: PIP overlay compositing ──
            if pip_layers:
                pip_result = self._apply_pip_overlay(
                    current_video, pip_layers, tmpdir, pw or 1920, ph or 1080,
                    fps or 30, vcodec, total_dur)
                if pip_result and _Path(pip_result).exists():
                    current_video = pip_result
                    logger.info(f"PIP overlay applied: {pip_result}")

            # ── Step 4: Mix audio tracks ──'''
if old_after_concat in ep:
    ep = ep.replace(old_after_concat, new_after_concat)
    changes.append("[FIX] export_panel.py: Added PIP overlay step (Step 3.5)")

# 2e. Add _apply_pip_overlay method before _mix_audio
pip_overlay_method = '''
    def _apply_pip_overlay(self, base_video, pip_layers, tmpdir, pw, ph, fps, vcodec, total_dur):
        """Overlay PIP layers onto the base video using FFmpeg overlay filter.

        Each PIP layer is scaled to 1/4 screen and positioned at bottom-right
        by default, unless clip has pip={x,y,w,h} overrides.

        Args:
            base_video: path to the base (V1) concatenated video
            pip_layers: list of {"track_name", "track_idx", "segments": [...]}
            tmpdir: temp directory for intermediate files
            pw, ph: output width, height
            fps: output framerate
            vcodec: video codec args list
            total_dur: total timeline duration

        Returns: path to composited video, or None on failure
        """
        self._sig.status.emit("Applying PIP overlay...")
        self._sig.progress.emit(55)

        current = base_video

        for layer_idx, layer in enumerate(pip_layers):
            segs = layer.get("segments", [])
            if not segs:
                continue

            layer_name = layer.get("track_name", f"PIP {layer_idx+1}")
            logger.info(f"PIP layer: {layer_name} ({len(segs)} segment(s))")

            for seg_idx, seg in enumerate(segs):
                seg_path = seg["path"]
                if not _Path(seg_path).exists():
                    logger.warning(f"PIP source not found: {seg_path}")
                    continue

                pip_cfg = seg.get("pip", {})
                # Default PIP: 1/4 size, bottom-right corner, 10px margin
                pip_w = pip_cfg.get("w", pw // 4)
                pip_h = pip_cfg.get("h", ph // 4)
                pip_x = pip_cfg.get("x", pw - pip_w - 20)
                pip_y = pip_cfg.get("y", ph - pip_h - 20)
                pip_opacity = pip_cfg.get("opacity", 1.0)

                tl_start = seg["timeline_start"]
                tl_end = seg["timeline_end"]
                in_pt = seg.get("in_point", 0)
                dur = tl_end - tl_start

                out_path = os.path.join(tmpdir, f"pip_{layer_idx}_{seg_idx}.mp4")

                # Build FFmpeg command with overlay filter
                # -ss on input for PIP source, enable overlay only during segment time
                filter_parts = []
                # Scale PIP input
                filter_parts.append(f"[1:v]scale={pip_w}:{pip_h}")
                if pip_opacity < 1.0:
                    alpha_val = pip_opacity
                    filter_parts[-1] += f",format=rgba,colorchannelmixer=aa={alpha_val}"
                filter_parts[-1] += "[pip]"

                # Overlay with enable condition (timeline-based)
                overlay_filter = (
                    f"[0:v][pip]overlay={pip_x}:{pip_y}:"
                    f"enable='between(t,{tl_start},{tl_end})'"
                )
                filter_complex = ";".join(filter_parts) + ";" + overlay_filter

                cmd = [
                    self._ffmpeg, "-y", "-hide_banner",
                    "-i", current,
                    "-ss", str(in_pt), "-t", str(dur), "-i", seg_path,
                    "-filter_complex", filter_complex,
                    "-c:v"] + list(vcodec) + [
                    "-c:a", "copy",
                    "-pix_fmt", "yuv420p",
                    out_path
                ]

                logger.info(f"PIP overlay cmd: {' '.join(cmd)}")

                try:
                    self._process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        creationflags=0x08000000)
                    _, stderr_bytes = self._process.communicate()
                    stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

                    if self._process.returncode != 0:
                        logger.error(f"PIP overlay failed: {stderr[-400:]}")
                        # Try CPU fallback if NVENC failed
                        if "nvenc" in stderr.lower() or "encoder" in stderr.lower():
                            logger.info("PIP: Retrying with CPU encoder...")
                            cpu_codec = ["libx264", "-preset", "medium", "-crf", "20"]
                            cmd_cpu = [c if c not in ["h264_nvenc", "p4"] else "" for c in cmd]
                            # Rebuild with CPU codec
                            cmd_cpu = [
                                self._ffmpeg, "-y", "-hide_banner",
                                "-i", current,
                                "-ss", str(in_pt), "-t", str(dur), "-i", seg_path,
                                "-filter_complex", filter_complex,
                                "-c:v"] + cpu_codec + [
                                "-c:a", "copy",
                                "-pix_fmt", "yuv420p",
                                out_path
                            ]
                            self._process = subprocess.Popen(
                                cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=0x08000000)
                            self._process.communicate()

                    if _Path(out_path).exists() and _Path(out_path).stat().st_size > 0:
                        current = out_path
                        logger.info(f"PIP segment applied: {seg_path} at ({pip_x},{pip_y}) {pip_w}x{pip_h}")
                    else:
                        logger.warning(f"PIP overlay produced no output for segment {seg_idx}")

                except Exception as e:
                    logger.error(f"PIP overlay error: {e}")
                    continue

        return current if current != base_video else None

'''

# Insert before _mix_audio
mix_audio_pos = ep.find("    def _mix_audio(")
if mix_audio_pos > 0 and "_apply_pip_overlay" not in ep:
    ep = ep[:mix_audio_pos] + pip_overlay_method + ep[mix_audio_pos:]
    changes.append("[FIX] export_panel.py: Added _apply_pip_overlay() method")

# 2f. Add PIP config defaults to clip_data when V2+ clips are added
# This goes in timeline_panel.py

if ep != ep_orig:
    ep_path.write_text(ep, encoding="utf-8")
    print(f"[SAVED] {ep_path}")

# ═══════════════════════════════════════════════════════════
# 3. timeline_panel.py — PIP 기본 속성 + 컨텍스트 메뉴
# ═══════════════════════════════════════════════════════════
tp_path = BASE_GUI / "timeline_panel.py"
tp = tp_path.read_text(encoding="utf-8")
tp_orig = tp

# 3a. ClipWidget contextMenuEvent — V2+ 비디오 클립에 PIP 설정 메뉴 추가
old_ctx_subtitle = '''        # Subtitle-specific actions
        act_edit_text = None
        act_merge_next = None
        if self._track_type == "subtitle":'''
new_ctx_subtitle = '''        # PIP settings for video clips on overlay tracks (V2+)
        act_pip_settings = None
        if self._track_type == "video":
            track_idx = self.clip_data.get("track", 0)
            canvas = self.parent()
            if canvas and hasattr(canvas, 'tracks'):
                # Count video tracks before this one
                vid_track_num = 0
                for ti, t in enumerate(canvas.tracks):
                    if t["type"] == "video":
                        vid_track_num += 1
                        if ti == track_idx:
                            break
                if vid_track_num > 1:  # V2 or higher
                    menu.addSeparator()
                    act_pip_settings = menu.addAction("PIP Settings...")

        # Subtitle-specific actions
        act_edit_text = None
        act_merge_next = None
        if self._track_type == "subtitle":'''
if old_ctx_subtitle in tp:
    tp = tp.replace(old_ctx_subtitle, new_ctx_subtitle)
    changes.append("[FIX] timeline_panel.py: ClipWidget — PIP Settings context menu for V2+")

# 3b. Handle PIP settings action
old_ctx_merge = '''        elif act_merge_next and action == act_merge_next:
            p = self.parent()
            if p and hasattr(p, "_merge_subtitle_clip"):
                p._merge_subtitle_clip(self)'''
new_ctx_merge = '''        elif act_merge_next and action == act_merge_next:
            p = self.parent()
            if p and hasattr(p, "_merge_subtitle_clip"):
                p._merge_subtitle_clip(self)
        elif act_pip_settings and action == act_pip_settings:
            p = self.parent()
            if p and hasattr(p, "_edit_pip_settings"):
                p._edit_pip_settings(self)'''
if old_ctx_merge in tp:
    tp = tp.replace(old_ctx_merge, new_ctx_merge)
    changes.append("[FIX] timeline_panel.py: ClipWidget — handle PIP Settings action")

# 3c. Add _edit_pip_settings to TimelineCanvas
pip_edit_method = '''
    def _edit_pip_settings(self, cw):
        """Open PIP settings dialog for overlay video clips."""
        pip = cw.clip_data.get("pip", {})
        from PyQt6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QDialogButtonBox

        dlg = QDialog(self.window())
        dlg.setWindowTitle("PIP Settings")
        dlg.setMinimumWidth(300)
        form = QFormLayout(dlg)

        spin_x = QSpinBox()
        spin_x.setRange(0, 3840)
        spin_x.setValue(pip.get("x", -1))
        spin_x.setSpecialValueText("Auto (right)")
        form.addRow("X Position:", spin_x)

        spin_y = QSpinBox()
        spin_y.setRange(0, 2160)
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

'''

# Insert before _edit_subtitle_text
edit_sub_pos = tp.find("    def _edit_subtitle_text(self, cw):")
if edit_sub_pos > 0 and "_edit_pip_settings" not in tp:
    tp = tp[:edit_sub_pos] + pip_edit_method + tp[edit_sub_pos:]
    changes.append("[FIX] timeline_panel.py: Added _edit_pip_settings() dialog")

if tp != tp_orig:
    tp_path.write_text(tp, encoding="utf-8")
    print(f"[SAVED] {tp_path}")

# ═══════════════════════════════════════════════════════════
# Compile check
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
for f in [pe_path, ep_path, tp_path]:
    try:
        py_compile.compile(str(f), doraise=True)
        print(f"[COMPILE OK] {f.name}")
    except py_compile.PyCompileError as e:
        print(f"[COMPILE ERROR] {f.name}: {e}")

print("=" * 60)
for c in changes:
    print(f"  {c}")
print(f"\nTotal: {len(changes)} changes")
print()
print("PIP 기능 구현 완료!")
print("실행: python -m aivideostudio.main")
print()
print("사용법:")
print("  1. V Video 1 트랙에 메인 비디오 배치")
print("  2. V Video 2 트랙에 오버레이(PIP) 비디오 배치")
print("  3. V2 클립 우클릭 → 'PIP Settings...' 로 위치/크기/투명도 설정")
print("  4. Export 시 자동으로 PIP 합성 적용")
print("  (기본값: 화면 1/4 크기, 우하단 배치)")
