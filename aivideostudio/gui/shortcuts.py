from PyQt6.QtGui import QShortcut, QKeySequence
from loguru import logger

KEYS = {
    "Space": "play_pause", "J": "reverse", "K": "stop", "L": "forward",
    "V": "select", "C": "razor", "Delete": "delete",
    
}

def setup_shortcuts(window):
    for key, action in KEYS.items():
        sc = QShortcut(QKeySequence(key), window)
        sc.activated.connect(lambda a=action: _do(window, a))

def _do(window, name):
    logger.debug(f"Shortcut: {name}")
    window.status_bar.showMessage(f"Action: {name}", 2000)
