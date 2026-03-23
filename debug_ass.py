# D:\aivideostudio\debug_ass.py
"""Debug: show generated ASS content and find the 3 bugs."""

pp_path = 'aivideostudio/gui/panels/preview_panel.py'
with open(pp_path, encoding='utf-8') as f:
    lines = f.readlines()

# 1) Show _generate_ass_content
print("=== _generate_ass_content ===")
for i, line in enumerate(lines):
    if 'def _generate_ass_content' in line:
        for j in range(i, min(i+80, len(lines))):
            print(f"{j+1:4d}: {line}" if j == i else f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def ') and '_generate_ass' not in lines[j]:
                break
        break

# 2) Show set_subtitle_events and _load_ass_to_mpv
print("\n\n=== set_subtitle_events + _load_ass_to_mpv ===")
for i, line in enumerate(lines):
    if 'def set_subtitle_events' in line:
        for j in range(i, min(i+30, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def ') and 'set_subtitle' not in lines[j] and '_load_ass' not in lines[j]:
                break
        break

# 3) Show _update_subtitle_overlay (bug: QLabel still showing alongside mpv)
print("\n\n=== _update_subtitle_overlay ===")
for i, line in enumerate(lines):
    if 'def _update_subtitle_overlay' in line:
        for j in range(i, min(i+20, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 4) Show _write_ass_temp
print("\n\n=== _write_ass_temp ===")
for i, line in enumerate(lines):
    if 'def _write_ass_temp' in line:
        for j in range(i, min(i+25, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 5) Check escape issues in the file
print("\n\n=== Lines with backslash issues ===")
for i, line in enumerate(lines, 1):
    if '\\\\\\\\' in line or ('\\\\fn' in line and 'tags.append' in line):
        print(f"  {i}: {line.rstrip()}")
