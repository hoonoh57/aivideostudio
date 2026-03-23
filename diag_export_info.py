# D:\aivideostudio\diag_export_info.py
"""Export Panel의 정보 수집 경로 진단"""
from pathlib import Path

ep = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
lines = ep.read_text(encoding="utf-8").splitlines()

# 1. set_input, set_subtitle 등 정보 설정 메서드
print("=" * 70)
print("1. Export Panel - 정보 설정 메서드들")
print("=" * 70)
for kw in ["def set_input", "def set_subtitle", "def set_playback",
           "_subtitle_path", "_input_path", "lbl_input", "lbl_sub"]:
    for i, l in enumerate(lines):
        if kw in l:
            print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 2. _subtitle_path 사용처
print("\n" + "=" * 70)
print("2. _subtitle_path 사용처")
print("=" * 70)
for i, l in enumerate(lines):
    if "_subtitle_path" in l:
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 3. set_subtitle 메서드 전체
print("\n" + "=" * 70)
print("3. set_subtitle 메서드")
print("=" * 70)
for i, l in enumerate(lines):
    if "def set_subtitle" in l:
        for j in range(i, min(i+15, len(lines))):
            print(f"  {j+1:5d}: {lines[j].rstrip()}")
            if j > i and lines[j].strip().startswith("def "):
                break
        break

# 4. set_input 메서드 전체
print("\n" + "=" * 70)
print("4. set_input 메서드")
print("=" * 70)
for i, l in enumerate(lines):
    if "def set_input" in l:
        for j in range(i, min(i+15, len(lines))):
            print(f"  {j+1:5d}: {lines[j].rstrip()}")
            if j > i and lines[j].strip().startswith("def "):
                break
        break

# 5. main_window.py에서 export_panel 호출
print("\n" + "=" * 70)
print("5. main_window.py - export_panel 호출")
print("=" * 70)
mw = Path(r"D:\aivideostudio\aivideostudio\gui\main_window.py")
mw_lines = mw.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(mw_lines):
    if "export_panel" in l.lower() and ("set_" in l or "subtitle" in l.lower() or "input" in l.lower()):
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 6. 자막 트랙에서 자막 파일 경로 가져오는 로직
print("\n" + "=" * 70)
print("6. 자막 관련 - main_window.py")
print("=" * 70)
for i, l in enumerate(mw_lines):
    if "subtitle" in l.lower() and ("path" in l.lower() or "set_sub" in l.lower() or "srt" in l.lower()):
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 7. _on_export에서 subtitle 처리
print("\n" + "=" * 70)
print("7. _on_export - subtitle 처리")
print("=" * 70)
for i, l in enumerate(lines):
    if "subtitle" in l.lower() and i > 190 and i < 270:
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")

# 8. 타임라인 트랙에서 자막 클립의 path 확인
print("\n" + "=" * 70)
print("8. playback_engine - subtitle 관련")
print("=" * 70)
pe = Path(r"D:\aivideostudio\aivideostudio\core\playback_engine.py")
pe_lines = pe.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(pe_lines):
    if "subtitle" in l.lower():
        print(f"  {i+1:5d}: {l.rstrip()[:140]}")
