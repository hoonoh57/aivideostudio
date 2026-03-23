# D:\aivideostudio\diag_clip_data.py
"""자막 클립의 clip_data에 subtitle_style이 있는지 런타임 확인"""
from pathlib import Path

# 1) timeline_panel에서 자막 편집 시 clip_data 업데이트 로직
TP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\timeline_panel.py")
tp_lines = TP.read_text(encoding="utf-8").split('\n')

print("=== timeline_panel: subtitle_style 관련 ===")
for i, line in enumerate(tp_lines):
    if 'subtitle_style' in line:
        print(f"  {i+1:4d} | {line.rstrip()}")

# 2) _edit_subtitle_text 메서드 전체
print("\n=== _edit_subtitle_text 메서드 ===")
for i, line in enumerate(tp_lines):
    if 'def _edit_subtitle_text' in line:
        for j in range(i, min(len(tp_lines), i+60)):
            print(f"  {j+1:4d} | {tp_lines[j]}")
            if j > i and tp_lines[j].strip().startswith('def ') and '_edit_subtitle_text' not in tp_lines[j]:
                break
        break

# 3) main_window에서 subtitle 편집 연결
MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
mw_lines = MW.read_text(encoding="utf-8").split('\n')

print("\n=== main_window: subtitle_style 설정 ===")
for i, line in enumerate(mw_lines):
    if 'subtitle_style' in line:
        for j in range(max(0, i-3), min(len(mw_lines), i+3)):
            print(f"  {j+1:4d} | {mw_lines[j].rstrip()}")
        print()

# 4) subtitle_panel에서 clip_data 업데이트
SP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\subtitle_panel.py")
sp_lines = SP.read_text(encoding="utf-8").split('\n')

print("\n=== subtitle_panel: clip_data / style 전달 ===")
for i, line in enumerate(sp_lines):
    if 'clip_data' in line or 'subtitle_style' in line or 'emit' in line:
        print(f"  {i+1:4d} | {line.rstrip()}")

# 5) preview_panel에서 subtitle_style 읽기
PP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\preview_panel.py")
pp_lines = PP.read_text(encoding="utf-8").split('\n')

print("\n=== preview_panel: subtitle_style 읽기 ===")
for i, line in enumerate(pp_lines):
    if 'subtitle_style' in line:
        for j in range(max(0, i-2), min(len(pp_lines), i+2)):
            print(f"  {j+1:4d} | {pp_lines[j].rstrip()}")
        print()
