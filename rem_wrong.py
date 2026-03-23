p = 'aivideostudio/gui/panels/timeline_panel.py'
lines = open(p, encoding='utf-8').readlines()
# Delete lines 1137-1139 (index 1136-1138)
del lines[1136:1139]
open(p, 'w', encoding='utf-8').writelines(lines)
# Verify
for i in range(1130, 1148):
    if i < len(lines):
        print(f'{i+1}: {repr(lines[i])}')
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print('SYNTAX: OK')
except py_compile.PyCompileError as e:
    print(f'SYNTAX ERROR: {e}')