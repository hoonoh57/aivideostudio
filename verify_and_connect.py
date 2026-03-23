# D:\aivideostudio\verify_and_connect.py
from pathlib import Path
import py_compile

BASE = Path(r"D:\aivideostudio")
tp = BASE / "aivideostudio" / "gui" / "panels" / "timeline_panel.py"
ep = BASE / "aivideostudio" / "gui" / "panels" / "export_panel.py"
mw = BASE / "aivideostudio" / "gui" / "main_window.py"

# Check main_window connection
mw_src = mw.read_text(encoding="utf-8")
if "set_timeline_canvas" not in mw_src:
    anchor = "self.export_panel.set_playback_engine(self.playback_engine)"
    idx = mw_src.find(anchor)
    if idx != -1:
        eol = mw_src.index("\n", idx)
        mw_src = mw_src[:eol+1] + "        self.export_panel.set_timeline_canvas(self.timeline_panel.canvas)\n" + mw_src[eol+1:]
        mw.write_text(mw_src, encoding="utf-8")
        print("[OK] main_window.py: set_timeline_canvas added")
else:
    print("[SKIP] main_window.py already has set_timeline_canvas")

print("\n=== Syntax Check ===")
all_ok = True
for f in [tp, ep, mw]:
    try:
        py_compile.compile(str(f), doraise=True)
        print(f"[COMPILE OK] {f.name}")
    except py_compile.PyCompileError as e:
        print(f"[COMPILE ERROR] {f.name}: {e}")
        all_ok = False

if all_ok:
    print("\nALL OK! Run: python -m aivideostudio.main")
    print("Then: git add -A && git commit -m \"v0.5.16: export In/Out range markers\" && git push")
