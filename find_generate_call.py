import os

for root, dirs, files in os.walk('aivideostudio'):
    for fn in files:
        if fn.endswith('.py'):
            fpath = os.path.join(root, fn)
            for i, line in enumerate(open(fpath, encoding='utf-8'), 1):
                if '.generate(' in line and 'thumbnail' in fpath.lower() or '.generate(' in line and 'ThumbnailEngine' in line:
                    print(f"{fpath}:{i}: {line.rstrip()}")
                if '.generate(' in line and 'engine' in line.lower():
                    print(f"{fpath}:{i}: {line.rstrip()}")

print("\n=== main_window.py lines 60-80 ===")
lines = open('aivideostudio/gui/main_window.py', encoding='utf-8').readlines()
for i in range(max(0,59), min(len(lines),80)):
    print(f"{i+1}: {lines[i].rstrip()}")
