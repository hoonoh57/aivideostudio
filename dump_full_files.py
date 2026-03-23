# D:\aivideostudio\dump_full_files.py
"""Dump full content of the two problematic files"""
from pathlib import Path

BASE = Path(r"D:\aivideostudio")

for name in [
    "aivideostudio/gui/panels/timeline_panel.py",
    "aivideostudio/gui/panels/export_panel.py",
]:
    f = BASE / name
    lines = f.read_text(encoding="utf-8").splitlines()
    print(f"\n{'='*70}")
    print(f"FILE: {name}  ({len(lines)} lines)")
    print(f"{'='*70}")
    for i, line in enumerate(lines, 1):
        print(f"{i:5d}: {line}")
