lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
print(f"Total lines: {len(lines)}")

# 1. _request_thumbnails method
print("\n=== _request_thumbnails ===")
for i, l in enumerate(lines):
    if 'def _request_thumbnails' in l:
        for j in range(i, min(i+30, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
else:
    print("NOT FOUND")

# 2. _reposition_all_clips method
print("\n\n=== _reposition_all_clips ===")
for i, l in enumerate(lines):
    if 'def _reposition_all_clips' in l:
        for j in range(i, min(i+20, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
else:
    print("NOT FOUND")

# 3. Track resize in mouseReleaseEvent (canvas)
print("\n\n=== _resizing_track reset ===")
for i, l in enumerate(lines):
    if '_resizing_track = -1' in l and i > 500:
        for j in range(max(0,i-5), min(i+5, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
else:
    print("NOT FOUND")
