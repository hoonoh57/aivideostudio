# D:\aivideostudio\show_export_and_paint.py
"""Show export panel + timeline paint for zone bar implementation."""

# 1) Export panel
import os
for root, dirs, fnames in os.walk('aivideostudio'):
    for fn in fnames:
        if 'export' in fn.lower() and fn.endswith('.py'):
            fp = os.path.join(root, fn)
            print(f"\n{'='*60}")
            print(f"FILE: {fp}")
            print('='*60)
            with open(fp, encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    print(f"{i:4d}: {line}", end='')

# 2) Timeline paintEvent
tp = 'aivideostudio/gui/panels/timeline_panel.py'
with open(tp, encoding='utf-8') as f:
    lines = f.readlines()

print(f"\n\n{'='*60}")
print("=== TimelineCanvas.paintEvent ===")
print('='*60)
for i, line in enumerate(lines):
    if 'def paintEvent' in line and i > 400:
        for j in range(i, min(i+80, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 3) Timeline keyPressEvent
print(f"\n\n=== keyPressEvent ===")
for i, line in enumerate(lines):
    if 'def keyPressEvent' in line and i > 400:
        for j in range(i, min(i+30, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+3 and lines[j].strip().startswith('def '):
                break
        break

# 4) Timeline __init__ for canvas
print(f"\n\n=== TimelineCanvas.__init__ ===")
for i, line in enumerate(lines):
    if 'class TimelineCanvas' in line:
        for j in range(i, min(i+50, len(lines))):
            print(f"{j+1:4d}: {lines[j]}", end='')
            if j > i+5 and lines[j].strip().startswith('def ') and '__init__' not in lines[j]:
                break
        break
