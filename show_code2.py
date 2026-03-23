lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()

# 1. _request_thumbnails 나머지 (on_done 이후)
print("=== _request_thumbnails continued (1063-1080) ===")
for i in range(1062, min(1080, len(lines))):
    print(f'{i+1}: {lines[i]}', end='')

# 2. TimelineCanvas의 mousePressEvent / mouseMoveEvent / mouseReleaseEvent
print("\n\n=== TimelineCanvas mouse events ===")
for i, l in enumerate(lines):
    if i > 480 and ('def mousePressEvent' in l or 'def mouseMoveEvent' in l or 'def mouseReleaseEvent' in l):
        print(f'\n--- {l.strip()} at line {i+1} ---')
        for j in range(i, min(i+40, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')

# 3. _update_size
print("\n\n=== _update_size ===")
for i, l in enumerate(lines):
    if 'def _update_size' in l:
        for j in range(i, min(i+10, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
