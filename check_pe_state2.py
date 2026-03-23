# D:\aivideostudio\check_pe_state2.py
"""정확한 패턴으로 재확인"""
from pathlib import Path

PE = Path(r"D:\aivideostudio\aivideostudio\core\playback_engine.py")
text = PE.read_text(encoding="utf-8")

print("=== 최종 체크리스트 ===")

# 1) elif로 PIP/base 분리 확인
has_elif = 'elif result["video"] is None:' in text
print(f"  PIP excluded from base (elif): {'YES ✅' if has_elif else 'NO ❌'}")

# 2) path 사용
has_path = 'clip.get("path", "")' in text
has_source = 'clip.get("source", "")' in text
print(f"  Uses 'path' (not 'source'):     {'YES ✅' if has_path and not has_source else 'NO ❌'}")

# 3) info["pip"] 전달
has_pip_info = 'info["pip"] = dict(clip["pip"])' in text
print(f"  PIP settings in video_layers:   {'YES ✅' if has_pip_info else 'NO ❌'}")

# 4) 컴파일
import py_compile
try:
    py_compile.compile(str(PE), doraise=True)
    print(f"  Compile:                        OK ✅")
except py_compile.PyCompileError as e:
    print(f"  Compile:                        ERROR ❌")

print("\n모두 ✅이면 → python -m aivideostudio.main 실행")
