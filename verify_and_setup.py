# D:\aivideostudio\verify_and_setup.py
"""전체 컴파일 검증 + C:\aistudio 구조 안내"""
import py_compile
from pathlib import Path

ROOT = Path(r"D:\aivideostudio")
SRC = ROOT / "aivideostudio"

# 1) 전체 컴파일 검증
print("=== 전체 컴파일 검증 ===")
all_py = sorted(SRC.rglob("*.py"))
ok = 0
fail = 0
for f in all_py:
    try:
        py_compile.compile(str(f), doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        fail += 1
        print(f"  [ERROR] {f.relative_to(ROOT)}: {e}")
print(f"  OK: {ok}, FAIL: {fail}")

# 2) 하드코딩 잔여 확인
print("\n=== 하드코딩 잔여 확인 ===")
import re
remaining = 0
for f in all_py:
    text = f.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines()):
        if line.strip().startswith("#"):
            continue
        # D:\ or D:/ hardcoded paths (not in comments/strings that are instructions)
        if re.search(r'["\']D:[/\\](?:aivideostudio|ffmpeg|GPT)', line):
            print(f"  {f.relative_to(ROOT)} line {i+1}: {line.strip()[:80]}")
            remaining += 1
print(f"  잔여 하드코딩: {remaining}개")

# 3) 설치 구조 안내
print(f"""
{'='*60}
C:\\aistudio 테스트 설치 순서:

1. 폴더 생성:
   mkdir C:\\aistudio

2. 소스 복사:
   xcopy /E /I D:\\aivideostudio\\aivideostudio C:\\aistudio\\aivideostudio
   copy D:\\aivideostudio\\pyproject.toml C:\\aistudio\\

3. FFmpeg 복사:
   xcopy /E /I D:\\ffmpeg C:\\aistudio\\ffmpeg

4. 가상환경 생성 + 의존성 설치:
   cd /d C:\\aistudio
   python -m venv .venv
   .venv\\Scripts\\activate
   pip install -e .
   (또는 pip install PyQt6 loguru appdirs Pillow numpy python-mpv pysrt)

5. 실행:
   cd /d C:\\aistudio
   python -m aivideostudio.main

6. 확인:
   - 콘솔에서 FFmpeg 경로가 C:\\aistudio\\ffmpeg\\bin\\ffmpeg.exe 로 표시
   - 기존 프로젝트 열기 정상 동작
{'='*60}
""")
