# D:\aivideostudio\fix_pip_dialog2.py
"""TimelineCanvas에 _edit_pip_settings 메서드 강제 추가"""
import py_compile
from pathlib import Path

tp_path = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
src = tp_path.read_text(encoding="utf-8")

# 확인: def _edit_pip_settings 가 실제로 있는지
has_def = "def _edit_pip_settings" in src
print(f"def _edit_pip_settings exists: {has_def}")

if not has_def:
    # _edit_subtitle_text 앞에 삽입
    target = "    def _edit_subtitle_text(self, cw):"
    
    if target not in src:
        # 대안: 클래스 내 다른 위치 찾기
        target = "    #  Subtitle Editing Methods"
        
    pip_method = '''    def _edit_pip_settings(self, cw):
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

'''
    if target in src:
        src = src.replace(target, pip_method + target)
        tp_path.write_text(src, encoding="utf-8")
        print(f"[SAVED] {tp_path}")
    else:
        print(f"[ERROR] Target not found: {target[:50]}")
else:
    print("[OK] _edit_pip_settings already defined")

try:
    py_compile.compile(str(tp_path), doraise=True)
    print("[COMPILE OK]")
except py_compile.PyCompileError as e:
    print(f"[COMPILE ERROR] {e}")

# 최종 검증
src2 = tp_path.read_text(encoding="utf-8")
for i, line in enumerate(src2.split('\n'), 1):
    if 'def _edit_pip_settings' in line:
        print(f"\n_edit_pip_settings method at line {i}")
