lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()

# 1. Check widget actual height at paintEvent time
print("=== paintEvent thumbnail condition ===")
for i, l in enumerate(lines):
    if 'THUMB_MIN_HEIGHT - 6' in l:
        for j in range(max(0, i-2), min(i+6, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break

# 2. Check r = self.rect() - what height does this return?
print("\n\n=== self.rect() in paintEvent ===")
for i, l in enumerate(lines):
    if 'self.rect().adjusted' in l and i < 200:
        print(f'{i+1}: {lines[i]}', end='')

# 3. TRACK_HEIGHT_MAX value
print(f"\n\n=== Constants ===")
for i, l in enumerate(lines):
    if i < 30 and ('TRACK_HEIGHT_MAX' in l or 'THUMB_MIN_HEIGHT' in l):
        print(f'{i+1}: {lines[i]}', end='')

# 4. _reposition_all_clips - does it call resize()?
print("\n\n=== _reposition_all_clips ===")
for i, l in enumerate(lines):
    if 'def _reposition_all_clips' in l:
        for j in range(i, min(i+15, len(lines))):
            print(f'{j+1}: {lines[j]}', end='')
        break
