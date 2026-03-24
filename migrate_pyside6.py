# D:\aivideostudio\migrate_pyside6.py
"""PyQt6 → PySide6 전환"""
import py_compile
from pathlib import Path

ROOT = Path(r"D:\aivideostudio")
SRC = ROOT / "aivideostudio"

all_py = sorted(SRC.rglob("*.py"))
converted = []
errors = []

print("=== PyQt6 → PySide6 전환 시작 ===\n")

for f in all_py:
    text = f.read_text(encoding="utf-8", errors="ignore")
    original = text
    rel = f.relative_to(ROOT)

    if "PyQt6" not in text and "pyqtSignal" not in text and "pyqtSlot" not in text:
        continue

    # 1) Module imports
    text = text.replace("from PyQt6.QtWidgets", "from PySide6.QtWidgets")
    text = text.replace("from PyQt6.QtCore", "from PySide6.QtCore")
    text = text.replace("from PyQt6.QtGui", "from PySide6.QtGui")
    text = text.replace("from PyQt6.QtMultimedia", "from PySide6.QtMultimedia")
    text = text.replace("from PyQt6.QtMultimediaWidgets", "from PySide6.QtMultimediaWidgets")
    text = text.replace("from PyQt6.QtSvg", "from PySide6.QtSvg")
    text = text.replace("from PyQt6.QtSvgWidgets", "from PySide6.QtSvgWidgets")
    text = text.replace("from PyQt6 import", "from PySide6 import")
    text = text.replace("import PyQt6", "import PySide6")

    # 2) Signal / Slot
    #    PyQt6: pyqtSignal → PySide6: Signal
    #    PyQt6: pyqtSlot   → PySide6: Slot
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        # Fix in import lines first
        if "from PySide6.QtCore import" in line:
            line = line.replace("pyqtSignal", "Signal")
            line = line.replace("pyqtSlot", "Slot")
        new_lines.append(line)
    text = "\n".join(new_lines)

    # Replace all remaining occurrences in class bodies
    text = text.replace("pyqtSignal", "Signal")
    text = text.replace("pyqtSlot", "Slot")

    if text != original:
        f.write_text(text, encoding="utf-8")
        converted.append(str(rel))
        print(f"  [OK] {rel}")

print(f"\n전환: {len(converted)}개 파일")

# Compile check
print("\n=== 컴파일 검증 ===")
ok = 0
fail = 0
for f in all_py:
    try:
        py_compile.compile(str(f), doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        fail += 1
        errors.append((f.relative_to(ROOT), str(e)))
        print(f"  [ERROR] {f.relative_to(ROOT)}: {e}")

print(f"  OK: {ok}, FAIL: {fail}")

# Verify no PyQt6 remnants
print("\n=== PyQt6 잔여 확인 ===")
remnants = 0
for f in all_py:
    text = f.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines()):
        if "PyQt6" in line or "pyqtSignal" in line or "pyqtSlot" in line:
            if not line.strip().startswith("#"):
                print(f"  {f.relative_to(ROOT)} line {i+1}: {line.strip()[:80]}")
                remnants += 1
print(f"  잔여: {remnants}개")

print(f"""
{'='*60}
  전환 파일: {len(converted)}개
  컴파일 OK: {ok}, FAIL: {fail}
  PyQt6 잔여: {remnants}개
{'='*60}

다음 단계:
  1. C:\\aistudio에 복사:
     xcopy /E /Y D:\\aivideostudio\\aivideostudio C:\\aistudio\\aivideostudio\\

  2. C:\\aistudio에서 테스트:
     cd /d C:\\aistudio
     .venv\\Scripts\\activate
     python -m aivideostudio.main
""")
