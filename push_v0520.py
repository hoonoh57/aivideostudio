# D:\aivideostudio\push_v0520.py
"""v0.5.20 커밋 & 푸시"""
import subprocess

def run(cmd):
    r = subprocess.run(cmd, shell=True, cwd=r"D:\aivideostudio", capture_output=True, text=True)
    print(r.stdout.strip())
    if r.stderr.strip():
        print(r.stderr.strip())

# Clean up diagnostic scripts to tools/
run("git add -A")
run('git commit -m "v0.5.20: style_locked serialize/restore - lock state persists across save/open"')
run("git push origin main")
print("\nDone!")
