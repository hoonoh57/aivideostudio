lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()
print(f"Total lines: {len(lines)}")

# 1. _request_thumbnails full body
print("\n=== _request_thumbnails (full) ===")
in_func = False
func_indent = 0
for i, l in enumerate(lines):
    if 'def _request_thumbnails' in l:
        in_func = True
        func_indent = len(l) - len(l.lstrip())
    if in_func:
        print(f"{i+1}: {l.rstrip()}")
        if i > 0 and in_func and l.strip().startswith('def ') and '_request_thumbnails' not in l:
            break

# 2. _on_filmstrip_ready full body 
print("\n=== _on_filmstrip_ready (full) ===")
in_func = False
for i, l in enumerate(lines):
    if 'def _on_filmstrip_ready' in l:
        in_func = True
    if in_func:
        print(f"{i+1}: {l.rstrip()}")
        if i > 0 and in_func and l.strip().startswith('def ') and '_on_filmstrip_ready' not in l:
            break

# 3. All lines with 'filmstrip' keyword
print("\n=== All 'filmstrip' references ===")
for i, l in enumerate(lines):
    if 'filmstrip' in l.lower():
        print(f"{i+1}: {l.rstrip()}")
