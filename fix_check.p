"""Diagnose: find exact line numbers of key anchors."""
p = "aivideostudio/gui/panels/timeline_panel.py"
lines = open(p, encoding="utf-8").readlines()
print(f"Total lines: {len(lines)}")
targets = [
    "TRACK_HEIGHT = 40",
    "TRACK_HEIGHT_MIN",
    "_track_y",
    "_track_at_y", 
    "_near_track_separator",
    "_resizing_track",
    '"height"',
    "_total_tracks_height",
    "def set_undo_manager",
    "def add_track(",
    "def add_clip(",
    "def _reposition_all_clips",
    "def _update_size",
    "def paintEvent",
    "def mousePressEvent",
    "def mouseMoveEvent",
    "def mouseReleaseEvent",
    "def keyPressEvent",
    "def dropEvent",
    "class TimelineCanvas",
    "class TimelinePanel",
]
for t in targets:
    found = [(i+1) for i, l in enumerate(lines) if t in l]
    status = f"lines {found}" if found else "NOT FOUND"
    print(f"  {t:40s} => {status}")
