# D:\aivideostudio\remove_pysrt.py
"""pysrt 의존성 제거 확인 및 정리"""
from pathlib import Path
import subprocess

ROOT = Path(r"D:\aivideostudio")
SRC = ROOT / "aivideostudio"

# 1) 전체 소스에서 pysrt, import srt 검색
print("=== pysrt / srt 사용 전수 조사 ===")
all_py = sorted(SRC.rglob("*.py"))
found = False
for f in all_py:
    text = f.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines()):
        if "pysrt" in line or ("import srt" in line and "pysubs" not in line):
            print(f"  {f.relative_to(ROOT)} line {i+1}: {line.rstrip()}")
            found = True

if not found:
    print("  pysrt 사용 없음! 안전하게 제거 가능\n")
    
    # Remove from requirements.txt
    req = ROOT / "requirements.txt"
    text = req.read_text(encoding="utf-8")
    new_lines = [l for l in text.splitlines() 
                 if "pysrt" not in l.lower()]
    req.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("[OK] requirements.txt에서 pysrt 제거")
    
    # Git commit
    def run(cmd):
        r = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True)
        if r.stdout.strip(): print(r.stdout.strip())
        if r.stderr.strip(): print(r.stderr.strip())
    
    run("git add -A")
    run('git commit -m "chore: remove pysrt (GPL) dependency - not used in source"')
    run("git push origin main")
    print("\n[OK] pysrt 제거 완료")
else:
    print("\n  pysrt가 사용 중 — 자체 파서로 교체 필요")
