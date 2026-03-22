p = "aivideostudio/gui/panels/timeline_panel.py"
lines = open(p, encoding="utf-8").readlines()
for i in range(818, 835):
    print(f"{i+1}: {repr(lines[i])}")