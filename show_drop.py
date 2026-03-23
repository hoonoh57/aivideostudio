# D:\aivideostudio\show_drop.py
lines = open('aivideostudio/gui/main_window.py', encoding='utf-8').readlines()
print("=== _on_timeline_drop ===")
in_func = False
for i, l in enumerate(lines):
    if 'def _on_timeline_drop' in l:
        in_func = True
    if in_func:
        print(f"{i+1}: {l.rstrip()}")
        if in_func and i > 0 and l.strip().startswith('def ') and '_on_timeline_drop' not in l:
            break
