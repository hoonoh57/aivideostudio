# D:\aivideostudio\show_preview_full.py
"""Show full preview panel and how mpv subtitle is configured."""

pp_path = 'aivideostudio/gui/panels/preview_panel.py'
with open(pp_path, encoding='utf-8') as f:
    lines = f.readlines()

print(f"=== preview_panel.py ({len(lines)} lines) FULL ===")
for i, line in enumerate(lines, 1):
    print(f"{i:4d}: {line}", end='')

print("\n\n=== main_window.py subtitle/preview related ===")
mw_path = 'aivideostudio/gui/main_window.py'
with open(mw_path, encoding='utf-8') as f:
    mw_lines = f.readlines()

# Show _refresh_subtitle_overlay and surrounding context
for i, line in enumerate(mw_lines):
    if '_refresh_subtitle_overlay' in line and 'def ' in line:
        start = max(0, i - 5)
        end = min(len(mw_lines), i + 40)
        print(f"\n--- main_window.py lines {start+1}-{end} ---")
        for j in range(start, end):
            print(f"{j+1:4d}: {mw_lines[j]}", end='')
        break

# Show export method that generates ASS
for i, line in enumerate(mw_lines):
    if 'def _export' in line or 'def export' in line:
        end = min(len(mw_lines), i + 50)
        print(f"\n--- main_window.py lines {i+1}-{end} (export) ---")
        for j in range(i, end):
            print(f"{j+1:4d}: {mw_lines[j]}", end='')
        break

# Show how subtitle_text is collected for export
for i, line in enumerate(mw_lines):
    if 'subtitle_text' in line and ('export' in mw_lines[max(0,i-10):i+1].__repr__().lower() 
                                     or 'ass' in line.lower() or 'srt' in line.lower()):
        start = max(0, i - 3)
        end = min(len(mw_lines), i + 5)
        print(f"\n--- main_window.py lines {start+1}-{end} ---")
        for j in range(start, end):
            print(f"{j+1:4d}: {mw_lines[j]}", end='')
