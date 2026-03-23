# D:\aivideostudio\show_subtitle_full.py
with open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8') as f:
    lines = f.readlines()

# Show _edit_subtitle_text full method
print("=== _edit_subtitle_text (full) ===")
for i, line in enumerate(lines):
    if '_edit_subtitle_text' in line and 'def ' in line:
        for j in range(i, min(i+40, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+2 and lines[j].strip() and not lines[j].startswith(' ' * 8) and lines[j].strip().startswith('def '):
                break
        break

print("\n\n=== _merge_subtitle_clip ===")
found = False
for i, line in enumerate(lines):
    if '_merge_subtitle_clip' in line and 'def ' in line:
        found = True
        for j in range(i, min(i+50, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+2 and lines[j].strip() and not lines[j].startswith(' ' * 8) and lines[j].strip().startswith('def '):
                break
        break
if not found:
    print("NOT FOUND - needs implementation")

# Show _notify_subtitle_changed
print("\n\n=== _notify_subtitle_changed ===")
for i, line in enumerate(lines):
    if '_notify_subtitle_changed' in line and 'def ' in line:
        for j in range(i, min(i+30, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+2 and lines[j].strip() and not lines[j].startswith(' ' * 8) and lines[j].strip().startswith('def '):
                break
        break

# Show subtitle_panel.py remainder
print("\n\n=== subtitle_panel.py (from line 130) ===")
with open('aivideostudio/gui/panels/subtitle_panel.py', encoding='utf-8') as f:
    sp_lines = f.readlines()
for i in range(129, len(sp_lines)):
    print(f"{i+1:4d}: {sp_lines[i]}", end='')

# Show all imports in timeline_panel.py (first 30 lines)
print("\n\n=== timeline_panel.py imports ===")
for i in range(min(30, len(lines))):
    print(f"{i+1:4d}: {lines[i]}", end='')
