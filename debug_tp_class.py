lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
# Find TimelinePanel class and its add_clip method
for i, l in enumerate(lines):
    if 'class TimelinePanel' in l:
        print(f"=== TimelinePanel starts at line {i+1} ===")
        for j in range(i, min(i+100, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
