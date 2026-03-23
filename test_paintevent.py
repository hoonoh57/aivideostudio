lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
for i, l in enumerate(lines):
    if 'def paintEvent' in l and i > 300:
        for j in range(i, min(i+80, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break