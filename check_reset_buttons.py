# D:\aivideostudio\check_reset_buttons.py
"""Reset 버튼 존재 여부 확인"""
from pathlib import Path

SED = Path(r"D:\aivideostudio\aivideostudio\gui\dialogs\subtitle_edit_dialog.py")
text = SED.read_text(encoding="utf-8")

print(f"btn_reset exists: {'btn_reset' in text}")
print(f"btn_reset_all exists: {'btn_reset_all' in text}")
print(f"_on_reset_default exists: {'_on_reset_default' in text}")
print(f"_on_reset_all_unstyled exists: {'_on_reset_all_unstyled' in text}")
print(f"_get_default_style exists: {'_get_default_style' in text}")
print(f"_apply_style_to_ui exists: {'_apply_style_to_ui' in text}")

# 해당 줄 출력
lines = text.split('\n')
for i, line in enumerate(lines):
    if 'btn_reset' in line and 'apply_all' not in line:
        print(f"  {i+1:4d} | {line.rstrip()}")
