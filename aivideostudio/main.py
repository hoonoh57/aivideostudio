import os, sys
from pathlib import Path

# Auto-detect libmpv DLL location (portable install support)
_app_root = Path(__file__).resolve().parent.parent
_dll_search = [
    _app_root,                          # <install_root>/
    _app_root / "aivideostudio",        # <install_root>/aivideostudio/
    _app_root / "mpv",                  # <install_root>/mpv/
    _app_root / "bin",                  # <install_root>/bin/
]
for _d in _dll_search:
    if (_d / "libmpv-2.dll").exists() or (_d / "mpv-2.dll").exists():
        os.environ["PATH"] = str(_d) + os.pathsep + os.environ.get("PATH", "")
        break

import sys
from aivideostudio.app import create_app

def main():
    app, window = create_app(sys.argv)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
