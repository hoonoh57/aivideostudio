# D:\aivideostudio\show_subtitle_dialog.py
import re

files_to_check = [
    'aivideostudio/gui/panels/timeline_panel.py',
    'aivideostudio/gui/dialogs/subtitle_edit_dialog.py',
    'aivideostudio/gui/dialogs/__init__.py',
]

for fpath in files_to_check:
    try:
        with open(fpath, encoding='utf-8') as f:
            lines = f.readlines()
        print(f"\n{'='*60}")
        print(f"FILE: {fpath} ({len(lines)} lines)")
        print('='*60)
        
        # Check if it's the dialog file - print full content
        if 'subtitle' in fpath.lower() or 'dialog' in fpath.lower():
            for i, line in enumerate(lines, 1):
                print(f"{i:4d}: {line}", end='')
            continue
        
        # For timeline_panel.py, find subtitle dialog related code
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in ['subtitleedit', 'subtitle_edit', 'subtitledialog', 'subtitle_dialog', 
                                                   'edit_subtitle', 'editsubtitle', '_open_subtitle', 'SubtitleEditDialog']):
                start = max(0, i - 3)
                end = min(len(lines), i + 20)
                print(f"\n--- {fpath} lines {start+1}-{end} ---")
                for j in range(start, end):
                    print(f"{j+1:4d}: {lines[j]}", end='')
                print()
    except FileNotFoundError:
        print(f"NOT FOUND: {fpath}")

# Also search for any subtitle dialog file
import os
for root, dirs, fnames in os.walk('aivideostudio'):
    for fn in fnames:
        if fn.endswith('.py') and ('subtitle' in fn.lower() or 'dialog' in fn.lower()):
            full = os.path.join(root, fn)
            if full.replace('\\','/') not in files_to_check:
                print(f"\n{'='*60}")
                print(f"FOUND EXTRA: {full}")
                print('='*60)
                with open(full, encoding='utf-8') as f:
                    content = f.read()
                print(content[:5000])
