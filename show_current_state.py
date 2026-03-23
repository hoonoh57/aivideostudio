# D:\aivideostudio\show_current_state.py
"""Show current code state for ASS export, preview integration, and undo."""

tp = 'aivideostudio/gui/panels/timeline_panel.py'
with open(tp, encoding='utf-8') as f:
    lines = f.readlines()

# 1) Show _edit_subtitle_text (current patched version)
print("=== _edit_subtitle_text (full, current) ===")
for i, line in enumerate(lines):
    if 'def _edit_subtitle_text' in line:
        for j in range(i, min(i+60, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def ') and 'subtitle_text' not in lines[j]:
                break
        break

# 2) Show _split_subtitle_clip
print("\n\n=== _split_subtitle_clip ===")
for i, line in enumerate(lines):
    if 'def _split_subtitle_clip' in line:
        for j in range(i, min(i+40, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 3) Show _merge_subtitle_clip (full)  
print("\n\n=== _merge_subtitle_clip (full) ===")
for i, line in enumerate(lines):
    if 'def _merge_subtitle_clip' in line:
        for j in range(i, min(i+60, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 4) Show subtitle_engine.py segments_to_ass
print("\n\n=== subtitle_engine.py: segments_to_ass ===")
with open('aivideostudio/engines/subtitle_engine.py', encoding='utf-8') as f:
    se_lines = f.readlines()
for i, line in enumerate(se_lines):
    if 'def segments_to_ass' in line or 'def _save_ass' in line:
        for j in range(i, min(i+40, len(se_lines))):
            print(f"{j+1:4d}: {se_lines[j]}", end='')
        break

# 5) Show how subtitles are exported/used in main_window or export
print("\n\n=== Export/refresh subtitle references ===")
import os
for root, dirs, fnames in os.walk('aivideostudio'):
    for fn in fnames:
        if not fn.endswith('.py'): continue
        fp = os.path.join(root, fn)
        with open(fp, encoding='utf-8') as f:
            content = f.read()
        for kw in ['_refresh_subtitle_overlay', 'subtitle_style', 'subtitle_text',
                    'build_ass', 'generate_ass', 'export_ass']:
            if kw in content:
                for li, line in enumerate(content.split('\n')):
                    if kw in line:
                        print(f"  {fp}:{li+1}: {line.strip()}")

# 6) Show preview_panel set_subtitle_events
print("\n\n=== preview_panel subtitle methods ===")
with open('aivideostudio/gui/panels/preview_panel.py', encoding='utf-8') as f:
    pp_lines = f.readlines()
for i, line in enumerate(pp_lines):
    if any(kw in line for kw in ['def set_subtitle', 'def _refresh', 'subtitle_events',
                                   'def load_subtitle', 'def update_subtitle']):
        for j in range(i, min(i+25, len(pp_lines))):
            print(f"{j+1:4d}: {pp_lines[j]}", end='')
            if j > i+2 and pp_lines[j].strip().startswith('def '):
                break
        print()

# 7) Show main_window _refresh_subtitle_overlay
print("\n\n=== main_window _refresh_subtitle_overlay ===")
with open('aivideostudio/gui/main_window.py', encoding='utf-8') as f:
    mw_lines = f.readlines()
for i, line in enumerate(mw_lines):
    if '_refresh_subtitle_overlay' in line and 'def ' in line:
        for j in range(i, min(i+30, len(mw_lines))):
            print(f"{j+1:4d}: {mw_lines[j]}", end='')
            if j > i+2 and mw_lines[j].strip().startswith('def '):
                break
        break
