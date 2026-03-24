# D:\aivideostudio\check_and_push.py
"""상태 확인 후 Git 커밋 & 푸시"""
import subprocess, sys

def run(cmd, cwd=r"D:\aivideostudio"):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() + ("\n" + r.stderr.strip() if r.stderr.strip() else "")

print("=== Git Status ===")
print(run("git status --short"))

print("\n=== Recent Commits (last 3) ===")
print(run("git log --oneline -3"))

print("\n=== Modified Files ===")
print(run("git diff --name-only"))

print("\n=== Untracked Files ===")
print(run("git ls-files --others --exclude-standard"))

print("\n=== Compile Check ===")
files = [
    r"aivideostudio\gui\dialogs\subtitle_edit_dialog.py",
    r"aivideostudio\gui\panels\timeline_panel.py",
    r"aivideostudio\gui\panels\export_panel.py",
    r"aivideostudio\gui\panels\preview_panel.py",
    r"aivideostudio\core\playback_engine.py",
    r"aivideostudio\gui\main_window.py",
]
import py_compile
from pathlib import Path
all_ok = True
for f in files:
    p = Path(r"D:\aivideostudio") / f
    if not p.exists():
        print(f"  [SKIP] {f} (not found)")
        continue
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"  [OK] {f}")
    except py_compile.PyCompileError as e:
        print(f"  [ERROR] {f}: {e}")
        all_ok = False

if not all_ok:
    print("\n[ABORT] Compile errors found. Fix before pushing.")
    sys.exit(1)

print("\n=== Committing & Pushing ===")
print(run("git add -A"))
msg = "v0.5.19: subtitle style management - Save as Default, Reset ALL to Default, Lock protection, PIP clip-based logic, typewriter export fix"
print(run(f'git commit -m "{msg}"'))
print(run("git push origin main"))
print("\nDone!")
