# D:\aivideostudio\diag_subtitle_issues.py
"""자막 효과 Export + 프로젝트 저장 진단"""
from pathlib import Path
import json

# ── 1) Export ASS 생성 로직 확인 ──
EP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\export_panel.py")
ep_lines = EP.read_text(encoding="utf-8").split('\n')

print("=== 1. Export: _generate_styled_ass 메서드 ===")
for i, line in enumerate(ep_lines):
    if 'def _generate_styled_ass' in line:
        for j in range(i, min(len(ep_lines), i+80)):
            print(f"  {j+1:4d} | {ep_lines[j]}")
        break

# ── 2) Preview ASS와 Export ASS 비교 ──
# 프리뷰에서 사용하는 ASS 생성 로직
PP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\preview_panel.py")
pp_lines = PP.read_text(encoding="utf-8").split('\n')

print("\n=== 2. Preview: ASS 생성 로직 (애니메이션 관련) ===")
for i, line in enumerate(pp_lines):
    if 'def _build_ass' in line or 'def _generate_ass' in line or 'karaoke' in line.lower() or 'typewriter' in line.lower() or '\\k' in line:
        for j in range(max(0, i-3), min(len(pp_lines), i+5)):
            print(f"  {j+1:4d} | {pp_lines[j]}")
        print()

# animation 키워드 검색
print("\n=== 3. Preview: animation/effect 관련 코드 ===")
for i, line in enumerate(pp_lines):
    if any(kw in line.lower() for kw in ['animation', 'animated', 'typewriter', 'karaoke', '\\k', 'effect']):
        print(f"  {i+1:4d} | {line.rstrip()}")

# ── 3) 프로젝트 저장 로직 확인 ──
PJ = Path(r"D:\aivideostudio\aivideostudio\core\project.py")
pj_lines = PJ.read_text(encoding="utf-8").split('\n')

print("\n=== 4. Project save: subtitle 관련 ===")
for i, line in enumerate(pj_lines):
    if any(kw in line.lower() for kw in ['subtitle', 'effect', 'animation', 'style', 'karaoke', 'save', 'serialize']):
        print(f"  {i+1:4d} | {line.rstrip()}")

# ── 4) .avs 파일 내용 확인 ──
avs = Path(r"C:\Users\haoru\Downloads\test.avs")
if avs.exists():
    data = json.loads(avs.read_text(encoding="utf-8"))
    print("\n=== 5. test.avs: subtitle clip 데이터 (첫 2개) ===")
    for track in data.get("tracks", []):
        if track.get("type") == "subtitle":
            for clip in track.get("clips", [])[:2]:
                print(json.dumps(clip, indent=2, ensure_ascii=False))
                print()
    # 전체 키 구조
    print("=== 6. test.avs: 최상위 키 ===")
    print(list(data.keys()))
    for track in data.get("tracks", []):
        print(f"  Track: {track.get('name')} keys_per_clip: ", end="")
        if track.get("clips"):
            print(list(track["clips"][0].keys()))
        else:
            print("(empty)")

# ── 5) subtitle_panel에서 effect/animation 저장 확인 ──
SP = Path(r"D:\aivideostudio\aivideostudio\gui\panels\subtitle_panel.py")
sp_lines = SP.read_text(encoding="utf-8").split('\n')

print("\n=== 7. SubtitlePanel: effect/animation/style 관련 ===")
for i, line in enumerate(sp_lines):
    if any(kw in line.lower() for kw in ['effect', 'animation', 'typewriter', 'karaoke', 'style', 'save_to_clip']):
        print(f"  {i+1:4d} | {line.rstrip()}")
