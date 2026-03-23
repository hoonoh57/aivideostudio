# D:\aivideostudio\diag_save_export2.py
"""저장/Export 로직 정밀 진단"""
from pathlib import Path

# ── 1) main_window.py에서 save 로직 확인 ──
MW = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
mw_lines = MW.read_text(encoding="utf-8").split('\n')

print(f"=== main_window.py ({len(mw_lines)} lines) ===")
print("\n--- _do_save 메서드 ---")
for i, line in enumerate(mw_lines):
    if '_do_save' in line and 'def ' in line:
        for j in range(i, min(len(mw_lines), i+50)):
            print(f"  {j+1:4d} | {mw_lines[j]}")
        break

# clip_data 직렬화 부분
print("\n--- clip_data / to_dict / serialize 검색 ---")
for i, line in enumerate(mw_lines):
    if any(kw in line for kw in ['clip_data', 'to_dict', 'serialize', 'subtitle_style', 'tracks']):
        print(f"  {i+1:4d} | {line.rstrip()}")

# ── 2) export_panel.py: _generate_styled_ass의 현재 bord~Dialogue 부분 ──
EP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
ep_lines = EP.read_text(encoding="utf-8").split('\n')

print(f"\n=== export_panel.py: _generate_styled_ass 현재 상태 (bord~end) ===")
for i, line in enumerate(ep_lines):
    if 'outline_size' in line and 'bord' in line:
        for j in range(i, min(len(ep_lines), i+25)):
            print(f"  {j+1:4d} | {ep_lines[j]}")
        break

# animation_tag 존재 여부
print(f"\n=== export_panel.py: animation_tag 검색 ===")
for i, line in enumerate(ep_lines):
    if 'animation' in line.lower() or 'typewriter' in line.lower() or '\\k' in line:
        print(f"  {i+1:4d} | {line.rstrip()}")
