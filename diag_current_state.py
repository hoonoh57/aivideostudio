# D:\aivideostudio\diag_current_state.py
"""현재 subtitle_edit_dialog.py와 timeline_panel.py 상태 점검"""
from pathlib import Path

SED = Path(r"D:\aivideostudio\aivideostudio\gui\dialogs\subtitle_edit_dialog.py")
TP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")

sed_text = SED.read_text(encoding="utf-8")
tp_text = TP.read_text(encoding="utf-8")

print(f"=== subtitle_edit_dialog.py ({len(sed_text.splitlines())} lines) ===")
print(f"  btn_apply_all: {'btn_apply_all' in sed_text}")
print(f"  btn_reset: {'btn_reset' in sed_text}")
print(f"  btn_reset_all: {'btn_reset_all' in sed_text}")
print(f"  btn_save_default: {'btn_save_default' in sed_text}")
print(f"  btn_reset_unstyled: {'btn_reset_unstyled' in sed_text or 'Reset All Unstyled' in sed_text}")
print(f"  _on_apply_all: {'_on_apply_all' in sed_text}")
print(f"  _on_reset_default: {'_on_reset_default' in sed_text}")
print(f"  _on_reset_all: {'_on_reset_all' in sed_text}")
print(f"  _on_save_default: {'_on_save_default' in sed_text}")
print(f"  lock / 잠금: {'lock' in sed_text.lower()}")

# Show all button definitions
print("\n--- 버튼 정의 ---")
for i, line in enumerate(sed_text.splitlines()):
    if any(kw in line for kw in ['QPushButton', 'btn_', 'addWidget(self.btn']):
        print(f"  {i+1:4d} | {line.rstrip()}")

print(f"\n=== timeline_panel.py paintEvent 스타일 뱃지 ===")
tp_lines = tp_text.splitlines()
for i, line in enumerate(tp_lines):
    if any(kw in line for kw in ['🎨', 'style_badge', 'subtitle_style', 'drawText']) and 130 <= i <= 250:
        print(f"  {i+1:4d} | {line.rstrip()}")

print(f"\n--- action 핸들러 ---")
for i, line in enumerate(tp_lines):
    if 'elif action ==' in line or 'if action ==' in line:
        if any(kw in line for kw in ['reset', 'apply', 'style']):
            print(f"  {i+1:4d} | {line.rstrip()}")
