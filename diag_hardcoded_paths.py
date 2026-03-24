# D:\aivideostudio\diag_hardcoded_paths.py
"""하드코딩된 경로 전수 조사"""
from pathlib import Path
import re

ROOT = Path(r"D:\aivideostudio")
SRC = ROOT / "aivideostudio"

all_py = sorted(SRC.rglob("*.py"))

# 검색 패턴: 드라이브 문자 + 절대경로
patterns = [
    (r'[A-Z]:\\[^\s"\']+', "Windows 절대경로"),
    (r'[A-Z]:/[^\s"\']+', "Windows 절대경로 (슬래시)"),
    (r'"D:\\', "D:\\ 하드코딩"),
    (r'"C:\\', "C:\\ 하드코딩"),
    (r"'D:\\", "D:\\ 하드코딩"),
    (r"'C:\\", "C:\\ 하드코딩"),
    (r'D:/aivideostudio', "D:/aivideostudio 하드코딩"),
    (r'D:\\aivideostudio', "D:\\aivideostudio 하드코딩"),
    (r'D:\\ffmpeg', "FFmpeg 경로 하드코딩"),
    (r'D:/ffmpeg', "FFmpeg 경로 하드코딩"),
]

print("=== 하드코딩된 경로 전수 조사 ===\n")

findings = {}
for f in all_py:
    text = f.read_text(encoding="utf-8", errors="ignore")
    rel = str(f.relative_to(ROOT))
    file_findings = []
    
    for i, line in enumerate(text.splitlines()):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        
        for pattern, desc in patterns:
            if re.search(pattern, line):
                file_findings.append((i + 1, desc, line.rstrip()))
                break  # One match per line is enough
    
    if file_findings:
        findings[rel] = file_findings

for rel, items in sorted(findings.items()):
    print(f"📄 {rel} ({len(items)} hits)")
    for lineno, desc, line in items:
        print(f"  {lineno:4d} | [{desc}] {line.strip()[:100]}")
    print()

print(f"{'='*60}")
print(f"  파일 수: {len(findings)}")
print(f"  총 하드코딩: {sum(len(v) for v in findings.values())}개")

# FFmpeg 경로 관련 설정 확인
print(f"\n=== config.py / settings 확인 ===")
config_files = list(SRC.rglob("config*.py")) + list(SRC.rglob("settings*.py")) + list(SRC.rglob("constants*.py"))
for f in config_files:
    print(f"\n📄 {f.relative_to(ROOT)}")
    text = f.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines()):
        if any(kw in line.lower() for kw in ['path', 'dir', 'ffmpeg', 'comfy', 'data_dir', 'root']):
            print(f"  {i+1:4d} | {line.rstrip()}")
