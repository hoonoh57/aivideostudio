# D:\aivideostudio\diag_subtitle_system.py
"""자막 시스템 전체 진단: 프리뷰 vs Export 비교"""
from pathlib import Path

BASE = Path(r"D:\aivideostudio\aivideostudio")

# 1. 프리뷰에서 자막을 어떻게 렌더링하는지
print("=" * 70)
print("1. preview_panel.py - 자막 렌더링")
print("=" * 70)
pp = BASE / "gui" / "panels" / "preview_panel.py"
pp_lines = pp.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(pp_lines):
    if any(kw in l.lower() for kw in ["subtitle", "sub_label", "sub_text", 
            "set_subtitle_events", "draw_sub", "_sub", "overlay",
            "font", "style", "ass", "paintEvent"]):
        if "def " in l or "class " in l or "self._sub" in l or "font" in l.lower() \
           or "style" in l.lower() or "subtitle_events" in l:
            print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 2. set_subtitle_events 메서드 전체
print("\n" + "=" * 70)
print("2. set_subtitle_events 전체")
print("=" * 70)
for i, l in enumerate(pp_lines):
    if "def set_subtitle_events" in l:
        indent = len(l) - len(l.lstrip())
        for j in range(i, len(pp_lines)):
            if j > i and pp_lines[j].strip().startswith("def ") and \
               (len(pp_lines[j]) - len(pp_lines[j].lstrip())) <= indent:
                break
            print(f"  {j+1:5d}: {pp_lines[j].rstrip()[:140]}")
        break

# 3. 자막 이벤트 구조 (SubtitleEngine에서 파싱)
print("\n" + "=" * 70)
print("3. subtitle_engine.py - 자막 파싱/이벤트 구조")
print("=" * 70)
for py_file in sorted(BASE.rglob("*.py")):
    src = py_file.read_text(encoding="utf-8", errors="replace")
    if "class SubtitleEngine" in src or "subtitle_engine" in py_file.stem:
        lines = src.splitlines()
        print(f"  File: {py_file}")
        for i, l in enumerate(lines):
            if any(kw in l for kw in ["def parse", "def load", "def generate",
                    "class Subtitle", "events", "def format", "def to_ass",
                    "def export", "def save", "ass_header", "Style:"]):
                print(f"    {i+1:5d}: {l.rstrip()[:140]}")

# 4. 프리뷰에서 자막 오버레이 그리기
print("\n" + "=" * 70)
print("4. 자막 오버레이 렌더링 (paintEvent / drawText)")  
print("=" * 70)
for i, l in enumerate(pp_lines):
    if "paint" in l.lower() or "draw" in l.lower() or "subtitle" in l.lower():
        if "def " in l or "drawText" in l or "QPainter" in l or \
           "sub" in l.lower() and ("label" in l.lower() or "text" in l.lower() or "overlay" in l.lower()):
            print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 5. subtitle_panel.py - 스타일 설정
print("\n" + "=" * 70)
print("5. subtitle_panel.py - 스타일 관련")
print("=" * 70)
sp = BASE / "gui" / "panels" / "subtitle_panel.py"
if sp.exists():
    sp_lines = sp.read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(sp_lines):
        if any(kw in l.lower() for kw in ["font", "style", "color", "size", "outline",
                "shadow", "margin", "ass", "export", "save", "to_ass"]):
            if "def " in l or "self." in l:
                print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 6. main_window에서 자막 export 로직
print("\n" + "=" * 70)
print("6. main_window.py - _export_subtitles / subtitle export")
print("=" * 70)
mw = BASE / "gui" / "main_window.py"
mw_lines = mw.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(mw_lines):
    if "def _export_subtitle" in l or "def _on_export_sub" in l:
        indent = len(l) - len(l.lstrip())
        for j in range(i, len(mw_lines)):
            if j > i + 1 and mw_lines[j].strip().startswith("def ") and \
               (len(mw_lines[j]) - len(mw_lines[j].lstrip())) <= indent:
                break
            print(f"  {j+1:5d}: {mw_lines[j].rstrip()[:140]}")
        break

# 7. 현재 자막 파일 내용 미리보기 (SRT)
print("\n" + "=" * 70)
print("7. SRT 파일 처음 10개 항목")
print("=" * 70)
srt_files = list(Path(r"D:\aivideostudio").glob("*.srt")) + \
            list(Path(r"C:\Users\haoru\Downloads").glob("*subtitle*.srt"))
for sf in srt_files[:2]:
    print(f"\n  File: {sf.name}")
    content = sf.read_text(encoding="utf-8", errors="replace").splitlines()
    for k, line in enumerate(content[:40]):
        print(f"    {line.rstrip()}")
