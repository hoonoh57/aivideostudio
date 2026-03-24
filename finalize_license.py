# D:\aivideostudio\finalize_license.py
"""라이선스 정리: pysrt(GPL) 확인 + requirements.txt 생성 + 커밋"""
import subprocess
from pathlib import Path

ROOT = Path(r"D:\aivideostudio")
SRC = ROOT / "aivideostudio"

# 1) pysrt 사용 현황
print("=== pysrt (GPL) 사용 현황 ===")
for f in sorted(SRC.rglob("*.py")):
    text = f.read_text(encoding="utf-8", errors="ignore")
    if "pysrt" in text:
        rel = f.relative_to(ROOT)
        print(f"  {rel}")
        for i, line in enumerate(text.splitlines()):
            if "pysrt" in line:
                print(f"    {i+1}: {line.rstrip()}")

# 2) requirements.txt 생성 (PySide6 기반)
req = """# AIVideoStudio dependencies (LGPL/MIT/BSD compatible)
PySide6>=6.6
loguru>=0.7
appdirs>=1.4
Pillow>=10.0
numpy>=1.24
python-mpv>=1.0
pysubs2>=1.7
requests>=2.31
pysrt>=1.1
# Note: pysrt is GPL - replace with self-built SRT parser before commercial release
"""
req_path = ROOT / "requirements.txt"
req_path.write_text(req, encoding="utf-8")
print(f"\n[SAVED] {req_path}")

# 3) Git commit & push
def run(cmd):
    r = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True)
    out = r.stdout.strip()
    if out: print(out)
    if r.stderr.strip(): print(r.stderr.strip())

print("\n=== Git ===")
run("git add -A")
run('git commit -m "v0.5.21: PyQt6->PySide6 (LGPL), portable paths, libmpv auto-detect, requirements.txt"')
run("git push origin main")

print(f"""
{'='*60}
라이선스 현황:
  ✅ PySide6 (LGPL) — 상업화 OK
  ✅ python-mpv (LGPL 선택) — 상업화 OK
  ✅ FFmpeg (외부 프로세스, LGPL) — 상업화 OK
  ✅ loguru, Pillow, numpy, pysubs2, requests — MIT/BSD
  ⚠️  pysrt (GPL) — 상업 배포 전 자체 파서로 교체 필요
  ⚠️  libmpv DLL — LGPL 빌드 사용 확인 필요

남은 작업:
  1. pysrt → 자체 SRT 파서 (50줄, 즉시 가능)
  2. libmpv LGPL 빌드 확보
  3. D 드라이브에서도 PySide6 전환 테스트
{'='*60}
""")
