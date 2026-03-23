# D:\aivideostudio\diag_subtitle_dialog.py
"""SubtitleEditDialog 구조 확인"""
from pathlib import Path

sed = Path(r"D:\aivideostudio\aivideostudio\gui\dialogs\subtitle_edit_dialog.py")
if sed.exists():
    lines = sed.read_text(encoding="utf-8").split('\n')
    print(f"subtitle_edit_dialog.py: {len(lines)} lines\n")
    for i, line in enumerate(lines):
        print(f"  {i+1:4d} | {line}")
else:
    import glob
    results = glob.glob(r"D:\aivideostudio\**\*subtitle*dialog*", recursive=True)
    print("Found:")
    for r in results:
        print(f"  {r}")
