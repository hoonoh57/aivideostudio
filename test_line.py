lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
for i in range(1130, 1150):
    if i < len(lines):
        print(f'{i+1}: {repr(lines[i])}')