lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()

# 1. _track_at_y - 반환값 확인 (tuple vs int)
print("=== _track_at_y ===")
for i, l in enumerate(lines):
    if 'def _track_at_y' in l:
        for j in range(i, min(i+12, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break

# 2. mousePressEvent에서 _track_at_y 호출 방식
print("\n\n=== _track_at_y usage in mousePressEvent ===")
for i, l in enumerate(lines):
    if '_track_at_y' in l and i > 1200 and i < 1250:
        print(f'{i+1}: {lines[i]}', end='')

# 3. add_clip 호출부 - track type 검사
print("\n\n=== add_clip full (570-590) ===")
for i in range(569, min(595, len(lines))):
    print(f'{i+1}: {lines[i]}', end='')

# 4. ClipWidget __init__ - _thumb_requested 초기값
print("\n\n=== ClipWidget __init__ thumb fields ===")
for i, l in enumerate(lines):
    if '_thumb_requested' in l and i < 100:
        print(f'{i+1}: {lines[i]}', end='')
