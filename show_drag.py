# D:\aivideostudio\show_drag.py
lines = open('aivideostudio/gui/panels/asset_panel.py', encoding='utf-8').readlines()
print(f"asset_panel.py: {len(lines)} lines\n")

# Find drag-related code
for i, l in enumerate(lines):
    if any(k in l.lower() for k in ['drag', 'mime', 'startdrag', 'mousemove', 'dropevent']):
        print(f"{i+1}: {l.rstrip()}")

print("\n=== timeline_panel.py drop events ===")
lines2 = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
for i, l in enumerate(lines2):
    if any(k in l.lower() for k in ['dropevent', 'dragevent', 'dragenter', 'dragmove', 'drop_requested', 'setacceptdrops']):
        print(f"{i+1}: {l.rstrip()}")
