# D:\aivideostudio\patch_export_range.py
"""
v0.5.16: Export Range Markers (In/Out Zone Bar on timeline ruler)
- TimelineCanvas: zone bar, draggable In/Out handles, I/O keys
- ExportPanel: range selector (Full / In-Out), filtered segments
"""
import re, shutil, textwrap
from pathlib import Path

BASE = Path(r"D:\aivideostudio")

# ─────────────────────────────────────────────────────────────
# 1. PATCH timeline_panel.py
# ─────────────────────────────────────────────────────────────
tp = BASE / "aivideostudio" / "gui" / "panels" / "timeline_panel.py"
src = tp.read_text(encoding="utf-8")

# 1a. Add zone bar constants after existing constants
zone_constants = textwrap.dedent("""\
# ── Zone Bar (In/Out export range) ──
ZONE_BAR_HEIGHT = 10
CLR_ZONE_BAR = QColor(40, 120, 255, 80)
CLR_ZONE_HANDLE = QColor(40, 120, 255, 220)
CLR_ZONE_BORDER = QColor(60, 150, 255, 200)
ZONE_HANDLE_WIDTH = 8
""")

# Insert after CLR_PLAYHEAD line
if "ZONE_BAR_HEIGHT" not in src:
    idx = src.find("CLR_PLAYHEAD")
    if idx != -1:
        eol = src.index("\n", idx)
        src = src[:eol+1] + "\n" + zone_constants + "\n" + src[eol+1:]
    print("[OK] Zone bar constants added")

# 1b. Add zone state to __init__
init_zone = textwrap.dedent("""\
        # ── Zone (In/Out) state ──
        self._zone_in = 0.0
        self._zone_out = 0.0  # 0 = unset (means full timeline)
        self._zone_enabled = False
        self._dragging_zone_in = False
        self._dragging_zone_out = False
        self._zone_visible = True
""")

if "_zone_in" not in src:
    # Insert before the line: self._dragging_playhead = False
    anchor = "self._dragging_playhead = False"
    idx = src.find(anchor)
    if idx != -1:
        src = src[:idx] + init_zone + "\n        " + src[idx:]
    print("[OK] Zone init state added")

# 1c. Add zone getter/setter methods after set_undo_manager
zone_methods = textwrap.dedent('''\
    # ── Zone (In/Out) API ──
    def get_zone(self):
        """Return (in_sec, out_sec, enabled). out=0 means full timeline."""
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
        """Return the QRect for the entire zone bar area (below ruler)."""
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

''')

if "def get_zone" not in src:
    anchor = "def set_undo_manager"
    idx = src.find(anchor)
    if idx != -1:
        # Find the end of set_undo_manager method
        next_def = src.find("\n    def ", idx + 10)
        if next_def != -1:
            src = src[:next_def] + "\n" + zone_methods + src[next_def:]
    print("[OK] Zone methods added")

# 1d. Update _track_y to account for zone bar offset
# We need to shift all tracks down by ZONE_BAR_HEIGHT
if "ZONE_BAR_HEIGHT" in src and "RULER_HEIGHT + ZONE_BAR_HEIGHT" not in src:
    # Find _track_y method and adjust
    track_y_pattern = r'(def _track_y\(self, idx\):.*?)(RULER_HEIGHT)'
    match = re.search(track_y_pattern, src, re.DOTALL)
    if match:
        # Replace RULER_HEIGHT with RULER_HEIGHT + ZONE_BAR_HEIGHT in _track_y
        old_func = "RULER_HEIGHT"
        # We need to be more targeted - find _track_y body
        ty_idx = src.find("def _track_y(self, idx):")
        if ty_idx != -1:
            # Find the RULER_HEIGHT in this method only (next ~5 lines)
            method_end = src.find("\n    def ", ty_idx + 10)
            method_body = src[ty_idx:method_end] if method_end != -1 else src[ty_idx:ty_idx+300]
            new_body = method_body.replace("RULER_HEIGHT", "(RULER_HEIGHT + ZONE_BAR_HEIGHT)", 1)
            src = src[:ty_idx] + new_body + (src[method_end:] if method_end != -1 else "")
            print("[OK] _track_y offset adjusted")

# 1e. Patch paintEvent to draw zone bar
zone_paint = textwrap.dedent("""\

        # ── Zone Bar (In/Out range) ──
        zone_y = RULER_HEIGHT
        zone_bar_rect = QRect(HEADER_WIDTH, zone_y, w - HEADER_WIDTH, ZONE_BAR_HEIGHT)
        p.fillRect(zone_bar_rect, QColor(30, 30, 35))
        if self._zone_enabled:
            zx_in = int(self._zone_in * self._pps) + HEADER_WIDTH
            z_out = self._zone_out if self._zone_out > 0 else self._total_duration
            zx_out = int(z_out * self._pps) + HEADER_WIDTH
            # Fill selected zone
            zone_sel = QRect(zx_in, zone_y, zx_out - zx_in, ZONE_BAR_HEIGHT)
            p.fillRect(zone_sel, CLR_ZONE_BAR)
            # Border
            p.setPen(QPen(CLR_ZONE_BORDER, 1))
            p.drawRect(zone_sel)
            # In handle
            p.fillRect(QRect(zx_in - 3, zone_y, 6, ZONE_BAR_HEIGHT), CLR_ZONE_HANDLE)
            p.setPen(QColor(255, 255, 255))
            p.setFont(_qf("Segoe UI", 7))
            p.drawText(zx_in + 4, zone_y + 8, "I")
            # Out handle
            p.fillRect(QRect(zx_out - 3, zone_y, 6, ZONE_BAR_HEIGHT), CLR_ZONE_HANDLE)
            p.drawText(zx_out - 10, zone_y + 8, "O")
        else:
            # Draw hint text
            p.setPen(QColor(80, 80, 90))
            p.setFont(_qf("Segoe UI", 8))
            p.drawText(zone_bar_rect, Qt.AlignmentFlag.AlignCenter,
                       "Press I / O to set export range")

""")

if "Zone Bar (In/Out range)" not in src:
    # Insert after ruler drawing, before snap lines
    anchor = "# Snap lines"
    idx = src.find(anchor)
    if idx != -1:
        src = src[:idx] + zone_paint + "        " + src[idx:]
    print("[OK] Zone bar paint added")

# 1f. Patch playhead line to extend through zone bar
# The playhead should draw from 0 to track_bottom (already does)

# 1g. Patch setMinimumHeight to include zone bar
if "RULER_HEIGHT + ZONE_BAR_HEIGHT + TRACK_HEIGHT" not in src:
    src = src.replace(
        "self.setMinimumHeight(RULER_HEIGHT + TRACK_HEIGHT * 4)",
        "self.setMinimumHeight(RULER_HEIGHT + ZONE_BAR_HEIGHT + TRACK_HEIGHT * 4)"
    )
    print("[OK] setMinimumHeight adjusted")

# 1h. Patch _total_tracks_height usage in paintEvent for track_bottom
# Adjust track_bottom to include zone bar
if "RULER_HEIGHT + self._total_tracks_height()" in src:
    src = src.replace(
        "RULER_HEIGHT + self._total_tracks_height()",
        "RULER_HEIGHT + ZONE_BAR_HEIGHT + self._total_tracks_height()"
    )
    print("[OK] track_bottom adjusted")

# 1i. Patch mousePressEvent, mouseMoveEvent, mouseReleaseEvent for zone dragging
# Find mousePressEvent and add zone handle detection
mouse_press_zone = textwrap.dedent("""\
        # ── Zone handle detection ──
        if self._zone_enabled:
            if self._zone_in_handle_rect().adjusted(-4, 0, 4, 0).contains(pos):
                self._dragging_zone_in = True
                return
            if self._zone_out_handle_rect().adjusted(-4, 0, 4, 0).contains(pos):
                self._dragging_zone_out = True
                return
        # Zone bar click to create/start zone
        zbar = self._zone_bar_rect()
        if zbar.contains(pos) and not self._zone_enabled:
            t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
            self._zone_in = t
            self._zone_out = min(t + 1.0, self._total_duration)
            self._zone_enabled = True
            self._dragging_zone_out = True
            self.update()
            return

""")

if "_dragging_zone_in = True" not in src:
    # Find mousePressEvent
    mp_idx = src.find("def mousePressEvent(self, event):")
    if mp_idx != -1:
        # Find the first line in the body after signature
        body_start = src.index("\n", mp_idx) + 1
        # Find pos = or event.position or similar
        # Insert after "pos = " line
        pos_line = src.find("pos = ", body_start)
        if pos_line != -1:
            eol = src.index("\n", pos_line)
            src = src[:eol+1] + "\n" + mouse_press_zone + src[eol+1:]
        print("[OK] mousePressEvent zone handling added")

# mouseMoveEvent zone handling
mouse_move_zone = textwrap.dedent("""\
        # ── Zone handle dragging ──
        if self._dragging_zone_in:
            t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
            self._zone_in = min(t, self._zone_out - 0.1) if self._zone_out > 0 else t
            self.update()
            return
        if self._dragging_zone_out:
            t = max(0, (pos.x() - HEADER_WIDTH) / self._pps)
            t = min(t, self._total_duration)
            self._zone_out = max(t, self._zone_in + 0.1)
            self.update()
            return
        # Zone handle cursor
        if self._zone_enabled:
            if (self._zone_in_handle_rect().adjusted(-4, 0, 4, 0).contains(pos) or
                    self._zone_out_handle_rect().adjusted(-4, 0, 4, 0).contains(pos)):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self._zone_bar_rect().contains(pos):
                self.setCursor(Qt.CursorShape.PointingHandCursor)

""")

if "_dragging_zone_in:" not in src:
    mm_idx = src.find("def mouseMoveEvent(self, event):")
    if mm_idx != -1:
        body_start = src.index("\n", mm_idx) + 1
        pos_line = src.find("pos = ", body_start)
        if pos_line != -1:
            eol = src.index("\n", pos_line)
            src = src[:eol+1] + "\n" + mouse_move_zone + src[eol+1:]
        print("[OK] mouseMoveEvent zone handling added")

# mouseReleaseEvent zone handling
mouse_release_zone = textwrap.dedent("""\
        # ── Zone handle release ──
        if self._dragging_zone_in or self._dragging_zone_out:
            self._dragging_zone_in = False
            self._dragging_zone_out = False
            if self._zone_out - self._zone_in < 0.1:
                self._zone_enabled = False
            self.update()
            return

""")

if "_dragging_zone_in or self._dragging_zone_out" not in src:
    mr_idx = src.find("def mouseReleaseEvent(self, event):")
    if mr_idx != -1:
        body_start = src.index("\n", mr_idx) + 1
        # Insert at beginning of method body
        # Find the first non-blank line
        next_line = src.find("        ", body_start)
        if next_line != -1:
            src = src[:next_line] + mouse_release_zone + "        " + src[next_line:]
        print("[OK] mouseReleaseEvent zone handling added")

# 1j. Patch keyPressEvent for I/O/Escape keys
key_zone = textwrap.dedent("""\
        elif event.key() == Qt.Key.Key_I:
            # Set zone In point at playhead
            self._zone_in = self._playhead
            if not self._zone_enabled:
                self._zone_out = self._total_duration
            if self._zone_out <= self._zone_in:
                self._zone_out = min(self._zone_in + 1.0, self._total_duration)
            self._zone_enabled = True
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_O:
            # Set zone Out point at playhead
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
""")

if "Key_I:" not in src or "zone In" not in src:
    # Find last elif in keyPressEvent (before the else or end)
    kp_idx = src.find("def keyPressEvent(self, event):")
    if kp_idx != -1:
        # Find 'event.accept()' for Key_Home (last handler)
        # Insert before the super() call or before else
        # Let's find the end of the existing key handlers
        # Search for "super().keyPressEvent" or end of method
        super_call = src.find("super().keyPressEvent", kp_idx)
        if super_call != -1:
            # Insert before super call
            line_start = src.rfind("\n", 0, super_call) + 1
            src = src[:line_start] + key_zone + "\n" + src[line_start:]
        else:
            # Find end of method
            next_def = src.find("\n    def ", kp_idx + 10)
            if next_def != -1:
                src = src[:next_def] + key_zone + "\n" + src[next_def:]
    print("[OK] I/O/Escape key bindings added")

# 1k. Fix ruler drawing position for clips - adjust all RULER_HEIGHT in
# clip drawing area references to (RULER_HEIGHT + ZONE_BAR_HEIGHT)
# But we already handled _track_y which is the main offset calculator

tp.write_text(src, encoding="utf-8")
print(f"[SAVED] {tp}")

# ─────────────────────────────────────────────────────────────
# 2. PATCH export_panel.py
# ─────────────────────────────────────────────────────────────
ep = BASE / "aivideostudio" / "gui" / "panels" / "export_panel.py"
ep_src = ep.read_text(encoding="utf-8")

# 2a. Add range selector combo in UI
range_ui = textwrap.dedent("""\

        # ── Export Range ──
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))
        self.combo_range = QComboBox()
        self.combo_range.addItems(["Full Timeline", "In-Out Range"])
        range_row.addWidget(self.combo_range)

        self.lbl_range_info = QLabel("")
        self.lbl_range_info.setStyleSheet("color: #88aaff; font-size: 11px;")
        range_row.addWidget(self.lbl_range_info)
        preset_lay.addLayout(range_row)

""")

if "combo_range" not in ep_src:
    # Insert after combo_preset row
    anchor = "preset_lay.addLayout(row)"
    idx = ep_src.find(anchor)
    if idx != -1:
        eol = ep_src.index("\n", idx)
        ep_src = ep_src[:eol+1] + range_ui + ep_src[eol+1:]
    print("[OK] Range selector UI added")

# 2b. Add _timeline_canvas reference and zone getter
zone_api = textwrap.dedent("""\
    def set_timeline_canvas(self, canvas):
        \"\"\"Connect to TimelineCanvas for zone (In/Out) range.\"\"\"
        self._timeline_canvas = canvas

    def _get_export_range(self):
        \"\"\"Return (start_sec, end_sec) or None for full timeline.\"\"\"
        if self.combo_range.currentText() == "In-Out Range":
            if hasattr(self, '_timeline_canvas') and self._timeline_canvas:
                z_in, z_out, enabled = self._timeline_canvas.get_zone()
                if enabled and z_out > z_in:
                    return (z_in, z_out)
        return None

    def update_range_info(self):
        \"\"\"Update the range info label from zone state.\"\"\"
        if hasattr(self, '_timeline_canvas') and self._timeline_canvas:
            z_in, z_out, enabled = self._timeline_canvas.get_zone()
            if enabled and z_out > z_in:
                dur = z_out - z_in
                m_in, s_in = divmod(int(z_in), 60)
                m_out, s_out = divmod(int(z_out), 60)
                m_d, s_d = divmod(int(dur), 60)
                self.lbl_range_info.setText(
                    f"[{m_in}:{s_in:02d} → {m_out}:{s_out:02d}] ({m_d}:{s_d:02d})")
                return
        self.lbl_range_info.setText("")

""")

if "set_timeline_canvas" not in ep_src:
    anchor = "def set_playback_engine"
    idx = ep_src.find(anchor)
    if idx != -1:
        ep_src = ep_src[:idx] + zone_api + "\n    " + ep_src[idx:]
    print("[OK] Zone API methods added to ExportPanel")

# 2c. Add _timeline_canvas init
if "self._timeline_canvas" not in ep_src:
    anchor = "self._playback_engine = None"
    idx = ep_src.find(anchor)
    if idx != -1:
        eol = ep_src.index("\n", idx)
        ep_src = ep_src[:eol+1] + "        self._timeline_canvas = None\n" + ep_src[eol+1:]
    print("[OK] _timeline_canvas init added")

# 2d. Modify _on_export to filter segments by range
# Replace the segment gathering and total_dur calculation
export_range_filter = textwrap.dedent("""\
        # Apply export range filter
        export_range = self._get_export_range()
        if export_range:
            range_start, range_end = export_range
            filtered = []
            for seg in segments:
                s_start = seg["timeline_start"]
                s_end = seg["timeline_end"]
                # Skip segments outside range
                if s_end <= range_start or s_start >= range_end:
                    continue
                new_seg = dict(seg)
                # Trim segment to range
                if s_start < range_start:
                    trim = range_start - s_start
                    new_seg["in_point"] = seg.get("in_point", 0) + trim
                    new_seg["timeline_start"] = range_start
                if s_end > range_end:
                    new_seg["timeline_end"] = range_end
                # Shift to zero-based timeline
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

""")

if "export_range = self._get_export_range()" not in ep_src:
    # Insert after "total_dur = max(...)" line
    anchor = "total_dur = max(s[\"timeline_end\"] for s in segments)"
    idx = ep_src.find(anchor)
    if idx != -1:
        eol = ep_src.index("\n", idx)
        # Replace the total_dur line with our ranged version
        line_start = ep_src.rfind("\n", 0, idx) + 1
        ep_src = ep_src[:line_start] + export_range_filter + ep_src[eol+1:]
    print("[OK] Export range filter added")

# 2e. Connect combo_range change to update_range_info
combo_connect = "\n        self.combo_range.currentIndexChanged.connect(lambda: self.update_range_info())\n"
if "combo_range.currentIndexChanged" not in ep_src:
    anchor = "self.btn_cancel.clicked.connect(self._on_cancel)"
    idx = ep_src.find(anchor)
    if idx != -1:
        eol = ep_src.index("\n", idx)
        ep_src = ep_src[:eol+1] + combo_connect + ep_src[eol+1:]
    print("[OK] Range combo signal connected")

ep.write_text(ep_src, encoding="utf-8")
print(f"[SAVED] {ep}")

# ─────────────────────────────────────────────────────────────
# 3. PATCH main_window.py - connect timeline canvas to export panel
# ─────────────────────────────────────────────────────────────
mw = BASE / "aivideostudio" / "gui" / "main_window.py"
mw_src = mw.read_text(encoding="utf-8")

# Find where export_panel is set up and add set_timeline_canvas
if "set_timeline_canvas" not in mw_src:
    # Look for set_playback_engine call on export panel
    anchor = "set_playback_engine"
    idx = mw_src.find(anchor)
    if idx != -1:
        eol = mw_src.index("\n", idx)
        # Find the variable name for export panel
        line_start = mw_src.rfind("\n", 0, idx) + 1
        line = mw_src[line_start:eol]
        # Extract panel variable (e.g., self.export_panel or self._export_panel)
        parts = line.strip().split(".")
        # Build the connection line
        # Find the canvas variable name - look for TimelineCanvas
        canvas_patterns = ["self._timeline_canvas", "self.timeline_canvas",
                           "self._canvas", "self.canvas"]
        export_patterns = ["self._export_panel", "self.export_panel",
                           "self._panel_export", "self.panel_export"]

        canvas_var = None
        export_var = None
        for cv in canvas_patterns:
            if cv in mw_src:
                canvas_var = cv
                break
        for ev in export_patterns:
            if ev in mw_src:
                export_var = ev
                break

        if canvas_var and export_var:
            connect_line = f"\n        {export_var}.set_timeline_canvas({canvas_var})\n"
            # Try to insert near set_playback_engine
            ep_call_idx = mw_src.find("set_playback_engine", idx)
            if ep_call_idx != -1:
                eol2 = mw_src.index("\n", ep_call_idx)
                mw_src = mw_src[:eol2+1] + connect_line + mw_src[eol2+1:]
                print(f"[OK] Connected {export_var}.set_timeline_canvas({canvas_var})")
        else:
            # Fallback: search more broadly
            # Look for TimelineCanvas() instantiation
            tc_idx = mw_src.find("TimelineCanvas(")
            if tc_idx != -1:
                # Get variable name
                line_start2 = mw_src.rfind("\n", 0, tc_idx) + 1
                assign_line = mw_src[line_start2:tc_idx].strip()
                if "=" in assign_line:
                    canvas_var = assign_line.split("=")[0].strip()
            # Look for ExportPanel instantiation
            ep_idx = mw_src.find("ExportPanel(")
            if ep_idx != -1:
                line_start3 = mw_src.rfind("\n", 0, ep_idx) + 1
                assign_line2 = mw_src[line_start3:ep_idx].strip()
                if "=" in assign_line2:
                    export_var = assign_line2.split("=")[0].strip()
            if canvas_var and export_var:
                # Insert after export panel creation
                eol3 = mw_src.index("\n", ep_idx)
                connect_line2 = f"\n        {export_var}.set_timeline_canvas({canvas_var})\n"
                mw_src = mw_src[:eol3+1] + connect_line2 + mw_src[eol3+1:]
                print(f"[OK] Connected {export_var}.set_timeline_canvas({canvas_var}) (fallback)")
            else:
                print("[WARN] Could not find canvas/export panel variables. Manual connection needed.")
                print(f"  canvas candidates: {canvas_var}")
                print(f"  export candidates: {export_var}")

    mw.write_text(mw_src, encoding="utf-8")
    print(f"[SAVED] {mw}")
else:
    print("[SKIP] main_window.py already has set_timeline_canvas")

# ─────────────────────────────────────────────────────────────
# 4. Syntax check
# ─────────────────────────────────────────────────────────────
import py_compile
errors = []
for f in [tp, ep, mw]:
    try:
        py_compile.compile(str(f), doraise=True)
        print(f"[COMPILE OK] {f.name}")
    except py_compile.PyCompileError as e:
        errors.append(str(e))
        print(f"[COMPILE ERROR] {f.name}: {e}")

print("\n" + "=" * 60)
if errors:
    print("ERRORS FOUND - check above")
else:
    print("ALL OK - run: python -m aivideostudio.main")
print("=" * 60)
