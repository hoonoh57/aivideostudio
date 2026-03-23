# D:\aivideostudio\check_pe_state.py
"""playback_engine.py 현재 상태 확인 — 수정 필요 여부 판별"""
from pathlib import Path

PE = Path(r"D:\aivideostudio\aivideostudio\core\playback_engine.py")
lines = PE.read_text(encoding="utf-8").split('\n')

print("=== Lines 88-100 (현재 상태) ===")
for i in range(87, min(105, len(lines))):
    print(f"  {i+1:4d} | {lines[i]}")

print("\n=== 체크리스트 ===")

# 1) PIP 클립이 base에서 제외되는지
has_pip_guard = any("not clip.get('pip')" in l and "result['video']" in l for l in lines)
print(f"  PIP clips excluded from base video: {'YES ✅' if has_pip_guard else 'NO ❌ (fix needed)'}")

# 2) source → path 수정 여부
has_source = any('clip.get("source", "")' in l for l in lines)
has_path = any('clip.get("path", "")' in l for l in lines)
print(f"  get_pip_video_layers uses 'path': {'YES ✅' if has_path and not has_source else 'NO ❌ (fix needed)'}")

# 3) info["pip"] 전달 여부
has_pip_info = any('info["pip"]' in l for l in lines)
print(f"  PIP settings passed in video_layers: {'YES ✅' if has_pip_info else 'NO ❌ (fix needed)'}")

# 4) 컴파일
import py_compile
try:
    py_compile.compile(str(PE), doraise=True)
    print(f"  Compile: OK ✅")
except py_compile.PyCompileError as e:
    print(f"  Compile: ERROR ❌ — {e}")
