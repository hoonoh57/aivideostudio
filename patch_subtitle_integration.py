# D:\aivideostudio\patch_subtitle_integration.py
"""
Patch 3 systems:
1. ASS tag generation from subtitle_style (subtitle_engine.py + main_window.py export)
2. Preview panel: styled subtitle overlay with per-event style
3. Undo/Redo: fix broken undo block in _edit_subtitle_text, add for split
"""
import os, py_compile, re

fixes = []

# ═══════════════════════════════════════════════════════════════
# 1. subtitle_engine.py — add style_to_ass_tags() + update segments_to_ass
# ═══════════════════════════════════════════════════════════════
se_path = 'aivideostudio/engines/subtitle_engine.py'
with open(se_path, encoding='utf-8') as f:
    se = f.read()

# Add helper function before class
helper_func = '''
def style_to_ass_tags(style: dict) -> str:
    """Convert subtitle_style dict to ASS override tags string."""
    if not style:
        return ""
    parts = []
    if style.get("font"):
        parts.append(r"\\fn" + style["font"])
    if style.get("size"):
        parts.append(r"\\fs" + str(style["size"]))
    if style.get("bold"):
        parts.append(r"\\b1")
    if style.get("italic"):
        parts.append(r"\\i1")
    if style.get("underline"):
        parts.append(r"\\u1")
    if style.get("font_color"):
        # ASS uses &HBBGGRR& format
        c = style["font_color"].lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            parts.append(r"\\c&H" + b + g + r + "&")
    if style.get("outline_color"):
        c = style["outline_color"].lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            parts.append(r"\\3c&H" + b + g + r + "&")
    if style.get("outline_size") is not None:
        parts.append(r"\\bord" + str(style["outline_size"]))
    if style.get("shadow") is False:
        parts.append(r"\\shad0")
    elif style.get("shadow") is True:
        parts.append(r"\\shad1")
    if style.get("bg_box"):
        parts.append(r"\\4a&H60&")  # semi-transparent bg
    if style.get("alignment"):
        parts.append(r"\\an" + str(style["alignment"]))
    # Animation tag (raw ASS)
    anim_tag = style.get("animation_tag", "")
    if anim_tag and anim_tag != "__TYPEWRITER__":
        parts.append(anim_tag.replace("{", "").replace("}", ""))
    if not parts:
        return ""
    return "{" + "".join(parts) + "}"

'''

if 'def style_to_ass_tags' not in se:
    # Insert before class SubtitleEngine:
    idx = se.find('class SubtitleEngine:')
    if idx > 0:
        se = se[:idx] + helper_func + '\n' + se[idx:]
        fixes.append("1a: style_to_ass_tags() added to subtitle_engine.py")

# Update segments_to_ass to accept style per segment
old_seg_to_ass = '''    @staticmethod
    def segments_to_ass(segments, output_path, fontname="Malgun Gothic",
                        fontsize=22, outline=2):
        subs = pysubs2.SSAFile()
        style = subs.styles["Default"]
        style.fontname = fontname
        style.fontsize = fontsize
        style.primarycolor = pysubs2.Color(255, 255, 255)
        style.outlinecolor = pysubs2.Color(0, 0, 0)
        style.outline = outline
        style.shadow = 1
        style.alignment = 2
        for seg in segments:
            event = pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=seg["text"]
            )
            subs.append(event)
        subs.save(str(output_path), format_="ass")
        logger.info(f"ASS saved: {output_path}")
        return str(output_path)'''

new_seg_to_ass = '''    @staticmethod
    def segments_to_ass(segments, output_path, fontname="Malgun Gothic",
                        fontsize=22, outline=2):
        subs = pysubs2.SSAFile()
        default = subs.styles["Default"]
        default.fontname = fontname
        default.fontsize = fontsize
        default.primarycolor = pysubs2.Color(255, 255, 255)
        default.outlinecolor = pysubs2.Color(0, 0, 0)
        default.outline = outline
        default.shadow = 1
        default.alignment = 2
        for seg in segments:
            text = seg["text"]
            # Apply per-subtitle style overrides as ASS tags
            seg_style = seg.get("style", {})
            if seg_style:
                tags = style_to_ass_tags(seg_style)
                if tags:
                    text = tags + text
            event = pysubs2.SSAEvent(
                start=int(seg["start"] * 1000),
                end=int(seg["end"] * 1000),
                text=text
            )
            subs.append(event)
        subs.save(str(output_path), format_="ass")
        logger.info(f"ASS saved: {output_path}")
        return str(output_path)'''

if old_seg_to_ass in se:
    se = se.replace(old_seg_to_ass, new_seg_to_ass)
    fixes.append("1b: segments_to_ass updated with per-segment style")

with open(se_path, 'w', encoding='utf-8') as f:
    f.write(se)

# ═══════════════════════════════════════════════════════════════
# 2. main_window.py — pass subtitle_style in events for preview + export
# ═══════════════════════════════════════════════════════════════
mw_path = 'aivideostudio/gui/main_window.py'
with open(mw_path, encoding='utf-8') as f:
    mw = f.read()

# Patch _refresh_subtitle_overlay to include style
old_refresh = '''    def _refresh_subtitle_overlay(self):
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
        self.preview.set_subtitle_events(events)'''

new_refresh = '''    def _refresh_subtitle_overlay(self):
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
        self.preview.set_subtitle_events(events)'''

if old_refresh in mw:
    mw = mw.replace(old_refresh, new_refresh)
    fixes.append("2a: _refresh_subtitle_overlay now passes style")

with open(mw_path, 'w', encoding='utf-8') as f:
    f.write(mw)

# ═══════════════════════════════════════════════════════════════
# 3. preview_panel.py — styled subtitle overlay rendering
# ═══════════════════════════════════════════════════════════════
pp_path = 'aivideostudio/gui/panels/preview_panel.py'
with open(pp_path, encoding='utf-8') as f:
    pp = f.read()

old_update_sub = '''    def _update_subtitle_overlay(self, tl_sec):
        text = ""
        for ev in self._subtitle_events:
            if ev["start"] <= tl_sec < ev["end"]:
                text = ev["text"]
                break
        if text != self._current_sub_text:
            self._current_sub_text = text
            if text:
                self._sub_label.setText(text)
                self._sub_label.show()
            else:
                self._sub_label.hide()'''

new_update_sub = '''    def _update_subtitle_overlay(self, tl_sec):
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

if old_update_sub in pp:
    pp = pp.replace(old_update_sub, new_update_sub)
    fixes.append("3: preview_panel styled subtitle overlay")

with open(pp_path, 'w', encoding='utf-8') as f:
    f.write(pp)

# ═══════════════════════════════════════════════════════════════
# 4. timeline_panel.py — fix undo/redo for edit, split, merge
# ═══════════════════════════════════════════════════════════════
tp_path = 'aivideostudio/gui/panels/timeline_panel.py'
with open(tp_path, encoding='utf-8') as f:
    tp = f.read()

# Replace entire _edit_subtitle_text with clean version including undo
old_edit_start = '    def _edit_subtitle_text(self, cw):'
old_edit_end_marker = '    def _split_subtitle_clip'

idx_start = tp.find(old_edit_start)
idx_end = tp.find(old_edit_end_marker)

if idx_start >= 0 and idx_end > idx_start:
    new_edit_method = '''    def _edit_subtitle_text(self, cw):
        """Open professional subtitle edit dialog."""
        from aivideostudio.gui.dialogs.subtitle_edit_dialog import SubtitleEditDialog
        from PyQt6.QtWidgets import QApplication
        win = None
        for w in QApplication.topLevelWidgets():
            if hasattr(w, 'timeline_panel'):
                win = w; break
        if win is None:
            win = self.window()
        # Check if there's a next subtitle on same track
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
        dlg = SubtitleEditDialog(cw.clip_data, has_next=has_next, parent=win)
        if dlg.exec() != SubtitleEditDialog.DialogCode.Accepted:
            return
        action = dlg.result_action
        data = dlg.result_data
        if action == "edit":
            old_text = cw.clip_data.get("subtitle_text", "")
            old_name = cw.clip_data.get("name", "")
            old_style = dict(cw.clip_data.get("subtitle_style", {}))
            new_text = data["text"]
            new_style = data["style"]
            cw.clip_data["subtitle_text"] = new_text
            cw.clip_data["name"] = new_text[:30] + ("..." if len(new_text) > 30 else "")
            cw.clip_data["subtitle_style"] = new_style
            cw.update()
            self._notify_subtitle_changed()
            if self._undo_manager:
                cid = getattr(cw, '_clip_id', -1)
                cv = self
                _ot, _on, _os = old_text, old_name, old_style
                _nt, _nn, _ns = new_text, cw.clip_data["name"], dict(new_style)
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
                                c.update(); cv._notify_subtitle_changed(); return
                self._undo_manager.push("Edit subtitle", undo_edit, redo_edit)
        elif action == "split":
            self._split_subtitle_clip(cw, data)
        elif action == "merge":
            self._merge_subtitle_clip(cw)

'''
    tp = tp[:idx_start] + new_edit_method + tp[idx_end:]
    fixes.append("4a: _edit_subtitle_text replaced with clean undo version")

# Replace _split_subtitle_clip to accept data dict from dialog
old_split_start = '    def _split_subtitle_clip'
old_split_end_marker = '    def _merge_subtitle_clip'

idx_s2 = tp.find(old_split_start)
idx_e2 = tp.find(old_split_end_marker)

if idx_s2 >= 0 and idx_e2 > idx_s2:
    new_split = '''    def _split_subtitle_clip(self, cw, data=None):
        """Split subtitle clip. If data provided (from dialog), use cursor split."""
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
            # Fallback: split at word boundary
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
            ti = track_idx
            cv = self
            _od = dict(old_data)
            _d1 = dict(c1d)
            _d2 = dict(c2d)
            _id1 = cw1._clip_id if cw1 else -1
            _id2 = cw2._clip_id if cw2 else -1
            def undo_split():
                for t in cv.tracks:
                    for c in list(t["clips"]):
                        try:
                            if not c._alive: continue
                        except RuntimeError: continue
                        cid = getattr(c, '_clip_id', -1)
                        if cid in (_id1, _id2):
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

'''
    tp = tp[:idx_s2] + new_split + tp[idx_e2:]
    fixes.append("4b: _split_subtitle_clip replaced with dialog-aware + undo version")

# Write back
with open(tp_path, 'w', encoding='utf-8') as f:
    f.write(tp)

# ═══════════════════════════════════════════════════════════════
# 5. subtitle_panel.py — update _save_ass to pass style per segment
# ═══════════════════════════════════════════════════════════════
sp_path = 'aivideostudio/gui/panels/subtitle_panel.py'
with open(sp_path, encoding='utf-8') as f:
    sp = f.read()

# Add import for style_to_ass_tags
if 'style_to_ass_tags' not in sp:
    old_import = 'import pysubs2'
    new_import = 'import pysubs2\nfrom aivideostudio.engines.subtitle_engine import style_to_ass_tags'
    if old_import in sp:
        sp = sp.replace(old_import, new_import, 1)
        fixes.append("5: subtitle_panel.py import style_to_ass_tags")

with open(sp_path, 'w', encoding='utf-8') as f:
    f.write(sp)

# ═══════════════════════════════════════════════════════════════
# 6. Compile checks
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("FIXES APPLIED:")
for f in fixes:
    print(f"  {f}")
print("=" * 60)

errors = []
for path in [se_path, mw_path, pp_path, tp_path, sp_path,
             'aivideostudio/gui/dialogs/subtitle_edit_dialog.py']:
    try:
        py_compile.compile(path, doraise=True)
        print(f"SYNTAX OK: {path}")
    except py_compile.PyCompileError as e:
        print(f"SYNTAX ERROR: {path}\n  {e}")
        errors.append(path)

if errors:
    print(f"\n*** {len(errors)} file(s) have syntax errors! ***")
else:
    print(f"\nAll {6} files OK. Run: python -m aivideostudio.main")
