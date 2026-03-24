# D:\aivideostudio\diag_default_style.py
"""기본 스타일 저장 경로 및 자막 생성 로직 확인"""
from pathlib import Path

# 1) config.py에서 data_dir 확인
CFG = Path(r"D:\aivideostudio\aivideostudio\config.py")
if CFG.exists():
    print("=== config.py ===")
    lines = CFG.read_text(encoding="utf-8").split('\n')
    for i, line in enumerate(lines):
        if 'data_dir' in line or 'AppData' in line or 'config' in line.lower():
            print(f"  {i+1:4d} | {line.rstrip()}")

# 2) 자막 생성 시 기본 스타일 어디서 설정되는지
# subtitle_panel.py에서 자막 클립 생성 로직
SP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\subtitle_panel.py")
sp_lines = SP.read_text(encoding="utf-8").split('\n')
print(f"\n=== subtitle_panel.py ({len(sp_lines)} lines) ===")
print("--- 자막 클립 생성/emit 관련 ---")
for i, line in enumerate(sp_lines):
    if any(kw in line for kw in ['clip_data', 'subtitle_style', 'default', 'emit', 'add_clip']):
        print(f"  {i+1:4d} | {line.rstrip()}")

# 3) main_window에서 자막을 타임라인에 추가하는 로직
MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
mw_lines = MW.read_text(encoding="utf-8").split('\n')
print(f"\n=== main_window.py: subtitle clip 생성 ===")
for i, line in enumerate(mw_lines):
    if 'subtitle' in line.lower() and ('add_clip' in line or 'clip_data' in line or 'subtitle_text' in line):
        for j in range(max(0, i-2), min(len(mw_lines), i+5)):
            print(f"  {j+1:4d} | {mw_lines[j].rstrip()}")
        print()

# 4) preview_panel에서 기본 자막 스타일
PP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\preview_panel.py")
pp_lines = PP.read_text(encoding="utf-8").split('\n')
print(f"\n=== preview_panel.py: 기본 자막 스타일/위치 ===")
for i, line in enumerate(pp_lines):
    if 'alignment' in line.lower() or 'position' in line.lower() or 'bottom' in line.lower():
        if 'subtitle' in pp_lines[max(0,i-5):i+1].__repr__().lower() or 'sub_label' in line:
            print(f"  {i+1:4d} | {line.rstrip()}")
