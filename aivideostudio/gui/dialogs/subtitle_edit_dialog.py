"""
SubtitleEditDialog - Professional subtitle editing dialog.
Benchmarked: DaVinci Resolve 20, Premiere Pro, CapCut.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QPlainTextEdit, QFontComboBox, QSpinBox,
    QComboBox, QGroupBox, QCheckBox, QFrame,
    QColorDialog, QDialogButtonBox, QSizePolicy, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush


# ASS \an alignment (numpad layout)
ALIGN_LABELS = {
    7: "\u2196", 8: "\u2191", 9: "\u2197",
    4: "\u2190", 5: "\u25cf", 6: "\u2192",
    1: "\u2199", 2: "\u2193", 3: "\u2198",
}

ANIMATION_PRESETS = [
    ("None",           ""),
    ("Fade In/Out",    r"{\fad(300,300)}"),
    ("Fade In (Long)", r"{\fad(800,0)}"),
    ("Fade Out (Long)",r"{\fad(0,800)}"),
    ("Typewriter",     "__TYPEWRITER__"),
    ("Slide Up",       r"{\move(<<cx>>,<<bot>>,<<cx>>,<<cy>>,0,300)}"),
    ("Scale Bounce",   r"{\fscx50\fscy50\t(0,200,\fscx100\fscy100)}"),
    ("Pop In",         r"{\fscx0\fscy0\t(0,150,\fscx105\fscy105)\t(150,250,\fscx100\fscy100)}"),
]


class _ColorButton(QPushButton):
    """Button showing its color as background."""
    color_changed = pyqtSignal(QColor)

    def __init__(self, initial: QColor, label: str, parent=None):
        super().__init__(label, parent)
        self._color = QColor(initial)
        self._update_style()
        self.clicked.connect(self._pick)
        self.setFixedHeight(28)
        self.setMinimumWidth(90)

    @property
    def color(self):
        return QColor(self._color)

    @color.setter
    def color(self, c: QColor):
        self._color = QColor(c)
        self._update_style()

    def _update_style(self):
        fg = "#000" if self._color.lightness() > 128 else "#fff"
        self.setStyleSheet(
            f"QPushButton{{background:{self._color.name()};color:{fg};"
            f"padding:3px 8px;border:1px solid #555;border-radius:3px;}}"
            f"QPushButton:hover{{border:1px solid #aaa;}}")

    def _pick(self):
        c = QColorDialog.getColor(self._color, self, self.text())
        if c.isValid():
            self._color = c
            self._update_style()
            self.color_changed.emit(c)


class _AlignGrid(QWidget):
    """3x3 grid for ASS alignment (numpad layout)."""
    alignment_changed = pyqtSignal(int)

    def __init__(self, current=2, parent=None):
        super().__init__(parent)
        self._current = current
        grid = QGridLayout(self)
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)
        self._btns = {}
        for row, codes in enumerate([(7, 8, 9), (4, 5, 6), (1, 2, 3)]):
            for col, code in enumerate(codes):
                b = QPushButton(ALIGN_LABELS[code])
                b.setFixedSize(28, 28)
                b.setCheckable(True)
                b.setChecked(code == current)
                b.clicked.connect(lambda checked, c=code: self._on_click(c))
                grid.addWidget(b, row, col)
                self._btns[code] = b

    def _on_click(self, code):
        self._current = code
        for c, b in self._btns.items():
            b.setChecked(c == code)
        self.alignment_changed.emit(code)

    @property
    def alignment(self):
        return self._current

    @alignment.setter
    def alignment(self, val):
        self._current = val
        for c, b in self._btns.items():
            b.setChecked(c == val)


class _LivePreview(QFrame):
    """Mini preview of styled subtitle."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 80)
        self.setStyleSheet("background:#1a1a2e; border:1px solid #444; border-radius:4px;")
        self._text = "Preview"
        self._font = QFont("Malgun Gothic", 18)
        self._color = QColor(255, 255, 255)
        self._outline_color = QColor(0, 0, 0)
        self._outline_size = 2
        self._bg_box = False
        self._bg_color = QColor(0, 0, 0, 160)
        self._alignment = 2
        self._bold = False
        self._italic = False
        self._underline = False
        self._shadow = True

    def update_style(self, **kw):
        for k, v in kw.items():
            if hasattr(self, f"_{k}"):
                setattr(self, f"_{k}", v)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1a1a2e"))
        if not self._text:
            p.end(); return
        font = QFont(self._font)
        font.setBold(self._bold)
        font.setItalic(self._italic)
        font.setUnderline(self._underline)
        p.setFont(font)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        w, h = self.width(), self.height()
        mg = 6
        an = self._alignment
        # horizontal
        if an in (1, 4, 7):   tx = mg
        elif an in (3, 6, 9): tx = w - tw - mg
        else:                  tx = (w - tw) // 2
        # vertical
        if an in (7, 8, 9):   ty = mg + fm.ascent()
        elif an in (4, 5, 6): ty = (h + fm.ascent() - fm.descent()) // 2
        else:                  ty = h - mg - fm.descent()
        # bg box
        if self._bg_box:
            pad = 4
            p.fillRect(tx - pad, ty - fm.ascent() - pad,
                        tw + pad * 2, fm.height() + pad * 2,
                        QBrush(self._bg_color))
        # shadow
        if self._shadow:
            p.setPen(QPen(QColor(0, 0, 0, 120)))
            p.drawText(tx + 1, ty + 1, self._text)
        # outline
        if self._outline_size > 0:
            p.setPen(QPen(self._outline_color))
            ofs = self._outline_size
            for dx in range(-ofs, ofs + 1):
                for dy in range(-ofs, ofs + 1):
                    if dx == 0 and dy == 0: continue
                    p.drawText(tx + dx, ty + dy, self._text)
        # main text
        p.setPen(QPen(self._color))
        p.drawText(tx, ty, self._text)
        p.end()


class SubtitleEditDialog(QDialog):
    """
    Professional subtitle editing dialog.
    Phase 1: Text edit, Split at cursor, Merge with next
    Phase 2: Font, size, color, bold/italic, outline, shadow, bg-box
    Phase 3: 9-point alignment
    Phase 4: Animation presets
    """
    def __init__(self, clip_data: dict, has_next: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Subtitle")
        self.setMinimumSize(580, 680)
        self.resize(620, 740)
        self._clip_data = dict(clip_data)
        self._has_next = has_next
        self.result_data = None
        self.result_action = None   # "edit" | "split" | "merge"
        self._build_ui()
        self._load_from_clip()
        self._connect_signals()
        self._refresh_preview()

    # ── Build UI ──────────────────────────────────────
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(8)

        # ── TIME INFO ──
        row_time = QHBoxLayout()
        self.lbl_time = QLabel("")
        self.lbl_time.setStyleSheet("color:#aaa; font-size:11px;")
        row_time.addWidget(self.lbl_time)
        row_time.addStretch()
        main.addLayout(row_time)

        # ── TEXT EDITOR ──
        grp_text = QGroupBox("Subtitle Text")
        lay_text = QVBoxLayout(grp_text)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setMinimumHeight(60)
        self.text_edit.setMaximumHeight(120)
        self.text_edit.setFont(QFont("Consolas", 11))
        self.text_edit.setPlaceholderText("Enter subtitle text...")
        lay_text.addWidget(self.text_edit)
        # Split / Merge
        row_act = QHBoxLayout()
        self.btn_split = QPushButton("\u2702  Split at Cursor")
        self.btn_split.setToolTip(
            "Split subtitle into two at cursor position.\n"
            "Time is proportionally divided by text length.")
        self.btn_split.setStyleSheet(
            "QPushButton{background:#e65100;color:white;padding:6px 12px;"
            "font-weight:bold;border-radius:3px;}"
            "QPushButton:hover{background:#ff6d00;}")
        row_act.addWidget(self.btn_split)
        self.btn_merge = QPushButton("\u2295  Merge with Next")
        self.btn_merge.setToolTip("Merge with the next subtitle on the same track.")
        self.btn_merge.setEnabled(self._has_next)
        self.btn_merge.setStyleSheet(
            "QPushButton{background:#1565c0;color:white;padding:6px 12px;"
            "font-weight:bold;border-radius:3px;}"
            "QPushButton:hover{background:#1976d2;}"
            "QPushButton:disabled{background:#555;color:#999;}")
        row_act.addWidget(self.btn_merge)
        row_act.addStretch()
        lay_text.addLayout(row_act)
        main.addWidget(grp_text)

        # ── STYLE ──
        grp_style = QGroupBox("Style")
        lay_s = QVBoxLayout(grp_style)
        # Font + Size
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        r1.addWidget(self.font_combo, 2)
        r1.addWidget(QLabel("Size:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(8, 200)
        self.spin_size.setValue(22)
        r1.addWidget(self.spin_size)
        lay_s.addLayout(r1)
        # B/I/U + Colors
        r2 = QHBoxLayout()
        self.chk_bold = QCheckBox("B")
        bf = QFont("Arial", 10, QFont.Weight.Bold)
        self.chk_bold.setFont(bf)
        self.chk_italic = QCheckBox("I")
        fi = QFont("Arial", 10); fi.setItalic(True)
        self.chk_italic.setFont(fi)
        self.chk_underline = QCheckBox("U")
        fu = QFont("Arial", 10); fu.setUnderline(True)
        self.chk_underline.setFont(fu)
        r2.addWidget(self.chk_bold)
        r2.addWidget(self.chk_italic)
        r2.addWidget(self.chk_underline)
        r2.addSpacing(12)
        self.btn_font_color = _ColorButton(QColor(255, 255, 255), "Font Color")
        r2.addWidget(self.btn_font_color)
        self.btn_outline_color = _ColorButton(QColor(0, 0, 0), "Outline Color")
        r2.addWidget(self.btn_outline_color)
        r2.addStretch()
        lay_s.addLayout(r2)
        # Outline + Shadow + BG
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Outline:"))
        self.spin_outline = QSpinBox()
        self.spin_outline.setRange(0, 10)
        self.spin_outline.setValue(2)
        r3.addWidget(self.spin_outline)
        self.chk_shadow = QCheckBox("Shadow")
        self.chk_shadow.setChecked(True)
        r3.addWidget(self.chk_shadow)
        self.chk_bg_box = QCheckBox("BG Box")
        r3.addWidget(self.chk_bg_box)
        self.btn_bg_color = _ColorButton(QColor(0, 0, 0, 160), "BG Color")
        self.btn_bg_color.setEnabled(False)
        r3.addWidget(self.btn_bg_color)
        r3.addStretch()
        lay_s.addLayout(r3)
        main.addWidget(grp_style)

        # ── POSITION ──
        grp_pos = QGroupBox("Position")
        lay_p = QHBoxLayout(grp_pos)
        lay_p.addWidget(QLabel("Alignment:"))
        self.align_grid = _AlignGrid(current=2)
        lay_p.addWidget(self.align_grid)
        lay_p.addStretch()
        main.addWidget(grp_pos)

        # ── ANIMATION ──
        grp_anim = QGroupBox("Animation Preset")
        lay_a = QHBoxLayout(grp_anim)
        lay_a.addWidget(QLabel("Effect:"))
        self.combo_anim = QComboBox()
        for name, _ in ANIMATION_PRESETS:
            self.combo_anim.addItem(name)
        self.combo_anim.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay_a.addWidget(self.combo_anim, 2)
        lay_a.addStretch()
        main.addWidget(grp_anim)

        # ── LIVE PREVIEW ──
        grp_prev = QGroupBox("Preview")
        lay_pv = QVBoxLayout(grp_prev)
        self.preview = _LivePreview()
        lay_pv.addWidget(self.preview)
        main.addWidget(grp_prev)

        # ── OK / Cancel ──
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self._on_ok)
        bbox.rejected.connect(self.reject)
        main.addWidget(bbox)

    # ── Load existing data ────────────────────────────
    def _load_from_clip(self):
        cd = self._clip_data
        self.text_edit.setPlainText(cd.get("subtitle_text", cd.get("name", "")))
        start = cd.get("timeline_start", 0)
        dur = cd.get("duration", 0)
        self.lbl_time.setText(
            f"Start: {start:.2f}s  |  End: {(start+dur):.2f}s  |  Duration: {dur:.2f}s")
        # Load per-subtitle style overrides
        style = cd.get("subtitle_style", {})
        if style.get("font"):
            self.font_combo.setCurrentFont(QFont(style["font"]))
        if style.get("size"):
            self.spin_size.setValue(style["size"])
        if style.get("bold"):
            self.chk_bold.setChecked(True)
        if style.get("italic"):
            self.chk_italic.setChecked(True)
        if style.get("underline"):
            self.chk_underline.setChecked(True)
        if style.get("font_color"):
            self.btn_font_color.color = QColor(style["font_color"])
        if style.get("outline_color"):
            self.btn_outline_color.color = QColor(style["outline_color"])
        if style.get("outline_size") is not None:
            self.spin_outline.setValue(style["outline_size"])
        if style.get("shadow") is not None:
            self.chk_shadow.setChecked(style["shadow"])
        if style.get("bg_box"):
            self.chk_bg_box.setChecked(True)
            self.btn_bg_color.setEnabled(True)
        if style.get("bg_color"):
            self.btn_bg_color.color = QColor(style["bg_color"])
        if style.get("alignment"):
            self.align_grid.alignment = style["alignment"]
        if style.get("animation"):
            for i, (name, _) in enumerate(ANIMATION_PRESETS):
                if name == style["animation"]:
                    self.combo_anim.setCurrentIndex(i)
                    break

    # ── Signal connections ────────────────────────────
    def _connect_signals(self):
        self.text_edit.textChanged.connect(self._refresh_preview)
        self.font_combo.currentFontChanged.connect(self._refresh_preview)
        self.spin_size.valueChanged.connect(self._refresh_preview)
        self.chk_bold.toggled.connect(self._refresh_preview)
        self.chk_italic.toggled.connect(self._refresh_preview)
        self.chk_underline.toggled.connect(self._refresh_preview)
        self.btn_font_color.color_changed.connect(self._refresh_preview)
        self.btn_outline_color.color_changed.connect(self._refresh_preview)
        self.spin_outline.valueChanged.connect(self._refresh_preview)
        self.chk_shadow.toggled.connect(self._refresh_preview)
        self.chk_bg_box.toggled.connect(self._on_bg_toggled)
        self.btn_bg_color.color_changed.connect(self._refresh_preview)
        self.align_grid.alignment_changed.connect(self._refresh_preview)
        self.combo_anim.currentIndexChanged.connect(self._refresh_preview)
        self.btn_split.clicked.connect(self._on_split)
        self.btn_merge.clicked.connect(self._on_merge)

    def _on_bg_toggled(self, checked):
        self.btn_bg_color.setEnabled(checked)
        self._refresh_preview()

    def _refresh_preview(self, *_args):
        txt = self.text_edit.toPlainText().strip() or "Preview"
        # Truncate for display
        display = txt[:60] + ("..." if len(txt) > 60 else "")
        font = QFont(self.font_combo.currentFont().family(),
                      self.spin_size.value())
        self.preview.update_style(
            text=display,
            font=font,
            color=self.btn_font_color.color,
            outline_color=self.btn_outline_color.color,
            outline_size=self.spin_outline.value(),
            bold=self.chk_bold.isChecked(),
            italic=self.chk_italic.isChecked(),
            underline=self.chk_underline.isChecked(),
            shadow=self.chk_shadow.isChecked(),
            bg_box=self.chk_bg_box.isChecked(),
            bg_color=self.btn_bg_color.color,
            alignment=self.align_grid.alignment,
        )

    # ── Collect result ────────────────────────────────
    def _collect_style(self):
        anim_name = self.combo_anim.currentText()
        anim_tag = ""
        for name, tag in ANIMATION_PRESETS:
            if name == anim_name:
                anim_tag = tag; break
        return {
            "font": self.font_combo.currentFont().family(),
            "size": self.spin_size.value(),
            "bold": self.chk_bold.isChecked(),
            "italic": self.chk_italic.isChecked(),
            "underline": self.chk_underline.isChecked(),
            "font_color": self.btn_font_color.color.name(),
            "outline_color": self.btn_outline_color.color.name(),
            "outline_size": self.spin_outline.value(),
            "shadow": self.chk_shadow.isChecked(),
            "bg_box": self.chk_bg_box.isChecked(),
            "bg_color": self.btn_bg_color.color.name(),
            "alignment": self.align_grid.alignment,
            "animation": anim_name,
            "animation_tag": anim_tag,
        }

    def _on_ok(self):
        self.result_action = "edit"
        self.result_data = {
            "text": self.text_edit.toPlainText().strip(),
            "style": self._collect_style(),
        }
        self.accept()

    def _on_split(self):
        text = self.text_edit.toPlainText()
        cursor_pos = self.text_edit.textCursor().position()
        if cursor_pos <= 0 or cursor_pos >= len(text):
            # Default: split in half
            cursor_pos = len(text) // 2
        text_before = text[:cursor_pos].strip()
        text_after = text[cursor_pos:].strip()
        if not text_before or not text_after:
            return  # nothing to split
        # Calculate time ratio
        total_len = len(text.strip())
        ratio = len(text_before) / total_len if total_len > 0 else 0.5
        self.result_action = "split"
        self.result_data = {
            "text_before": text_before,
            "text_after": text_after,
            "ratio": ratio,
            "style": self._collect_style(),
        }
        self.accept()

    def _on_merge(self):
        self.result_action = "merge"
        self.result_data = {
            "text": self.text_edit.toPlainText().strip(),
            "style": self._collect_style(),
        }
        self.accept()
