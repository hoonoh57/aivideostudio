# D:\aivideostudio\patch_real_subtitle_render.py
"""
Major patch: Real subtitle rendering via mpv ASS + styled QLabel fallback + export with styles.
"""
import os, py_compile, tempfile

fixes = []

# ═══════════════════════════════════════════════════════════════
# 1. preview_panel.py — mpv ASS subtitle + positioned QLabel
# ═══════════════════════════════════════════════════════════════
pp_path = 'aivideostudio/gui/panels/preview_panel.py'
with open(pp_path, encoding='utf-8') as f:
    pp = f.read()

# --- 1a: Add tempfile import ---
if 'import tempfile' not in pp:
    pp = pp.replace('import os, sys, time as _time', 'import os, sys, time as _time, tempfile', 1)
    fixes.append("1a: added tempfile import")

# --- 1b: Add _ass_tmp_path attribute in __init__ ---
old_init_end = "self._build_ui()"
new_init_end = """self._ass_tmp_path = None
        self._last_applied_style = None
        self._build_ui()"""
if '_ass_tmp_path' not in pp:
    pp = pp.replace(old_init_end, new_init_end, 1)
    fixes.append("1b: added _ass_tmp_path in __init__")

# --- 1c: Replace resizeEvent to support alignment ---
old_resize = '''    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self._video_wrapper.width()
        h = self._video_wrapper.height()
        self._container.setGeometry(0, 0, w, h)
        sub_h = 50
        self._sub_label.setGeometry(20, h - sub_h - 10, w - 40, sub_h)'''

new_resize = '''    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self._video_wrapper.width()
        h = self._video_wrapper.height()
        self._container.setGeometry(0, 0, w, h)
        self._reposition_sub_label()

    def _reposition_sub_label(self):
        """Position subtitle label based on current alignment."""
        w = self._video_wrapper.width()
        h = self._video_wrapper.height()
        sub_h = 50
        margin = 10
        an = getattr(self, '_current_sub_alignment', 2)
        # Vertical: top(7,8,9), middle(4,5,6), bottom(1,2,3)
        if an in (7, 8, 9):
            y = margin
        elif an in (4, 5, 6):
            y = (h - sub_h) // 2
        else:
            y = h - sub_h - margin
        self._sub_label.setGeometry(20, y, w - 40, sub_h)'''

if old_resize in pp:
    pp = pp.replace(old_resize, new_resize)
    fixes.append("1c: resizeEvent supports alignment positioning")

# --- 1d: Replace _update_subtitle_overlay + _apply_subtitle_style ---
old_sub_block = '''    def _update_subtitle_overlay(self, tl_sec):
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
            self._sub_label.setAlignment(QtC.AlignmentFlag.AlignCenter)'''

new_sub_block = '''    def _update_subtitle_overlay(self, tl_sec):
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
        # Also update mpv ASS subtitle if available
        self._update_mpv_ass_subtitle(tl_sec)

    def _apply_subtitle_style(self, style):
        """Apply per-subtitle style to the overlay QLabel (visual fallback)."""
        if not style:
            self._sub_label.setStyleSheet(
                "QLabel{color:white; font-size:15px; background:rgba(0,0,0,160);"
                "padding:4px 12px; border-radius:4px; font-weight:bold;"
                "font-family:'Malgun Gothic',sans-serif;}")
            self._current_sub_alignment = 2
            self._reposition_sub_label()
            return
        font_name = style.get("font", "Malgun Gothic")
        font_size = style.get("size", 22)
        preview_size = max(11, min(int(font_size * 0.7), 32))
        fc = style.get("font_color", "#ffffff")
        oc = style.get("outline_color", "#000000")
        bold = "bold" if style.get("bold") else "normal"
        italic = "italic" if style.get("italic") else "normal"
        underline = "underline" if style.get("underline") else "none"
        bg = "rgba(0,0,0,170)" if style.get("bg_box") else "rgba(0,0,0,0)"
        an = style.get("alignment", 2)
        self._current_sub_alignment = an
        # Text shadow via CSS
        shadow_css = ""
        outline_size = style.get("outline_size", 2)
        if outline_size > 0:
            shadow_parts = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0: continue
                    shadow_parts.append(f"{dx}px {dy}px 0px {oc}")
            shadow_css = f"text-shadow: {', '.join(shadow_parts)};"
        if style.get("shadow"):
            shadow_css += f" text-shadow: 2px 2px 3px rgba(0,0,0,0.8);"
        # Horizontal alignment
        if an in (1, 4, 7):
            h_align = "left"
        elif an in (3, 6, 9):
            h_align = "right"
        else:
            h_align = "center"
        self._sub_label.setStyleSheet(
            f"QLabel{{"
            f"color:{fc}; font-family:'{font_name}'; font-size:{preview_size}px;"
            f"font-weight:{bold}; font-style:{italic}; text-decoration:{underline};"
            f"background:{bg}; padding:6px 14px; border-radius:4px;"
            f"text-align:{h_align}; {shadow_css}"
            f"}}")
        from PyQt6.QtCore import Qt as _Qt
        if an in (1, 4, 7):
            self._sub_label.setAlignment(_Qt.AlignmentFlag.AlignLeft | _Qt.AlignmentFlag.AlignVCenter)
        elif an in (3, 6, 9):
            self._sub_label.setAlignment(_Qt.AlignmentFlag.AlignRight | _Qt.AlignmentFlag.AlignVCenter)
        else:
            self._sub_label.setAlignment(_Qt.AlignmentFlag.AlignCenter)
        self._reposition_sub_label()

    def _generate_ass_content(self):
        """Generate a temporary ASS file from current subtitle events with styles."""
        if not self._subtitle_events:
            return None
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Malgun Gothic,22,&H00FFFFFF,&H000000FF,"
            "&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,30,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        for ev in self._subtitle_events:
            s = ev["start"]
            e = ev["end"]
            text = ev.get("text", "")
            style = ev.get("style", {})
            # Build ASS override tags
            tags = []
            if style.get("font"):
                tags.append(f"\\\\fn{style['font']}")
            if style.get("size"):
                tags.append(f"\\\\fs{style['size']}")
            if style.get("bold"):
                tags.append("\\\\b1")
            if style.get("italic"):
                tags.append("\\\\i1")
            if style.get("underline"):
                tags.append("\\\\u1")
            if style.get("font_color"):
                c = style["font_color"].lstrip("#")
                if len(c) == 6:
                    r, g, b = c[0:2], c[2:4], c[4:6]
                    tags.append(f"\\\\c&H{b}{g}{r}&")
            if style.get("outline_color"):
                c = style["outline_color"].lstrip("#")
                if len(c) == 6:
                    r, g, b = c[0:2], c[2:4], c[4:6]
                    tags.append(f"\\\\3c&H{b}{g}{r}&")
            if style.get("outline_size") is not None:
                tags.append(f"\\\\bord{style['outline_size']}")
            if style.get("shadow") is False:
                tags.append("\\\\shad0")
            if style.get("bg_box"):
                tags.append("\\\\4a&H60&")
            if style.get("alignment"):
                tags.append(f"\\\\an{style['alignment']}")
            # Animation
            anim = style.get("animation_tag", "")
            if anim and anim != "__TYPEWRITER__":
                clean = anim.replace("{", "").replace("}", "")
                tags.append(clean)
            elif anim == "__TYPEWRITER__":
                # Typewriter: reveal char by char using \\k
                dur_ms = int((e - s) * 1000)
                char_count = max(1, len(text.replace("\\N", "")))
                per_char = max(1, dur_ms // char_count)
                tw_text = ""
                for ch in text:
                    if ch in ("\\\\", "{", "}"):
                        tw_text += ch
                    else:
                        tw_text += f"{{\\\\k{per_char // 10}}}{ch}"
                tag_prefix = "{" + "".join(tags) + "}" if tags else ""
                text = tag_prefix + tw_text
                tags = []  # already embedded
            tag_str = ""
            if tags:
                tag_str = "{" + "".join(tags) + "}"
            # Format time: H:MM:SS.CC
            def fmt_ass_time(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s2 = sec % 60
                return f"{h}:{m:02d}:{s2:05.2f}"
            line = (f"Dialogue: 0,{fmt_ass_time(s)},{fmt_ass_time(e)},"
                    f"Default,,0,0,0,,{tag_str}{text}")
            lines.append(line)
        return "\\n".join(lines)

    def _write_ass_temp(self):
        """Write current subtitle events as a temp ASS file and return path."""
        content = self._generate_ass_content()
        if not content:
            return None
        # Use real newlines
        content = content.replace("\\\\n", "\\n").replace("\\n", chr(10))
        try:
            if self._ass_tmp_path and os.path.exists(self._ass_tmp_path):
                os.unlink(self._ass_tmp_path)
        except Exception:
            pass
        try:
            fd, path = tempfile.mkstemp(suffix=".ass", prefix="aivs_sub_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
            self._ass_tmp_path = path
            return path
        except Exception as e:
            logger.warning(f"Failed to write temp ASS: {e}")
            return None

    def _update_mpv_ass_subtitle(self, tl_sec):
        """Load ASS subtitle into mpv for proper rendering."""
        pass  # mpv sub-file loading is done once via set_subtitle_events

    def set_subtitle_events(self, events):
        self._subtitle_events = events or []
        logger.info(f"Preview: loaded {len(self._subtitle_events)} subtitle events")
        # Generate and load ASS into mpv
        self._load_ass_to_mpv()

    def _load_ass_to_mpv(self):
        """Generate temp ASS and load into mpv player."""
        if not self._player:
            return
        # Remove existing subtitle tracks
        try:
            self._player.command("sub-remove")
        except Exception:
            pass
        if not self._subtitle_events:
            return
        ass_path = self._write_ass_temp()
        if ass_path:
            try:
                self._player.command("sub-add", ass_path, "select")
                logger.info(f"mpv: ASS subtitle loaded ({len(self._subtitle_events)} events)")
            except Exception as e:
                logger.warning(f"mpv sub-add failed: {e}")'''

if old_sub_block in pp:
    pp = pp.replace(old_sub_block, new_sub_block)
    fixes.append("1d: full subtitle rendering with mpv ASS + styled QLabel + positioning")
else:
    print("WARNING: Could not find old subtitle block for replacement.")
    print("Trying line-by-line search...")
    # Show what we're looking for
    target = '_update_subtitle_overlay'
    for i, line in enumerate(pp.split('\n')):
        if target in line:
            print(f"  Found '{target}' at line {i+1}: {line.strip()}")

# --- 1e: Cleanup in closeEvent ---
old_close = '''    def closeEvent(self, event):
        self._timer.stop()
        for p in (self._player, self._audio_player):
            if p:
                try: p.terminate()
                except Exception: pass
        self._player = None
        self._audio_player = None
        super().closeEvent(event)'''

new_close = '''    def closeEvent(self, event):
        self._timer.stop()
        # Clean up temp ASS file
        try:
            if self._ass_tmp_path and os.path.exists(self._ass_tmp_path):
                os.unlink(self._ass_tmp_path)
        except Exception:
            pass
        for p in (self._player, self._audio_player):
            if p:
                try: p.terminate()
                except Exception: pass
        self._player = None
        self._audio_player = None
        super().closeEvent(event)'''

if old_close in pp:
    pp = pp.replace(old_close, new_close)
    fixes.append("1e: closeEvent cleans temp ASS")

with open(pp_path, 'w', encoding='utf-8') as f:
    f.write(pp)

# ═══════════════════════════════════════════════════════════════
# 2. main_window.py — export with styles
# ═══════════════════════════════════════════════════════════════
mw_path = 'aivideostudio/gui/main_window.py'
with open(mw_path, encoding='utf-8') as f:
    mw = f.read()

old_export = '''    def _export_subtitles_from_timeline(self):
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
            logger.error(f"Subtitle export failed: {e}")'''

new_export = '''    def _export_subtitles_from_timeline(self):
        """Export current timeline subtitle clips as SRT/ASS file with styles."""
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
                    "style": cd.get("subtitle_style", {}),
                })
        events.sort(key=lambda e: e["start"])
        if not events:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export", "No subtitle clips on timeline.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Subtitles", "subtitles.ass",
            "ASS (*.ass);;SRT (*.srt);;All (*.*)")
        if not path:
            return
        try:
            import pysubs2
            from aivideostudio.engines.subtitle_engine import style_to_ass_tags
            subs = pysubs2.SSAFile()
            # Set default style
            default = subs.styles["Default"]
            default.fontname = "Malgun Gothic"
            default.fontsize = 22
            default.primarycolor = pysubs2.Color(255, 255, 255)
            default.outlinecolor = pysubs2.Color(0, 0, 0)
            default.outline = 2
            default.shadow = 1
            default.alignment = 2
            fmt = "ass" if path.endswith(".ass") else "srt"
            for ev in events:
                text = ev["text"]
                if fmt == "ass" and ev.get("style"):
                    tags = style_to_ass_tags(ev["style"])
                    if tags:
                        text = tags + text
                subs.append(pysubs2.SSAEvent(
                    start=int(ev["start"] * 1000),
                    end=int(ev["end"] * 1000),
                    text=text))
            subs.save(path, format_=fmt)
            self.status_bar.showMessage(
                f"Subtitles exported: {Path(path).name} ({len(events)} entries)", 5000)
            logger.info(f"Subtitles exported: {path} (format={fmt})")
        except Exception as e:
            self.status_bar.showMessage(f"Export failed: {e}", 5000)
            logger.error(f"Subtitle export failed: {e}")'''

if old_export in mw:
    mw = mw.replace(old_export, new_export)
    fixes.append("2: export with ASS style tags + default ASS format")

with open(mw_path, 'w', encoding='utf-8') as f:
    f.write(mw)

# ═══════════════════════════════════════════════════════════════
# 3. Compile checks
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("FIXES APPLIED:")
for f in fixes:
    print(f"  {f}")
print("=" * 60)

errors = []
for path in [pp_path, mw_path, 'aivideostudio/engines/subtitle_engine.py',
             'aivideostudio/gui/dialogs/subtitle_edit_dialog.py',
             'aivideostudio/gui/panels/timeline_panel.py']:
    try:
        py_compile.compile(path, doraise=True)
        print(f"SYNTAX OK: {path}")
    except py_compile.PyCompileError as e:
        print(f"SYNTAX ERROR: {path}\n  {e}")
        errors.append(path)

if errors:
    print(f"\n*** {len(errors)} file(s) have syntax errors ***")
else:
    print(f"\nAll files OK. Run: python -m aivideostudio.main")
