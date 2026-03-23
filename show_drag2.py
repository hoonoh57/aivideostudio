# D:\aivideostudio\show_drag2.py
lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()

print("=== Lines 1095-1130 (drag/drop area) ===")
for i in range(max(0, 1094), min(len(lines), 1130)):
    print(f"{i+1}: {lines[i].rstrip()}")

print("\n=== Search for dragEnterEvent ===")
for i, l in enumerate(lines):
    if 'dragEnterEvent' in l:
        print(f"{i+1}: {l.rstrip()}")

if not any('dragEnterEvent' in l for l in lines):
    print("NOT FOUND - this is the bug!")
