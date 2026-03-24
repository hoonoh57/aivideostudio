"""Global keyboard shortcuts — deferred binding."""
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import QTimer
from loguru import logger


def setup_shortcuts(window):
    """Set up global keyboard shortcuts. Deferred so panels exist."""

    def _bind():
        tp = getattr(window, 'timeline_panel', None)
        pv = getattr(window, 'preview', None)
        if not tp or not pv:
            logger.warning("Shortcuts: panels not ready, retry...")
            QTimer.singleShot(200, _bind)
            return

        def _do(name, fn):
            def wrapper():
                logger.debug(f"Shortcut: {name}")
                fn()
            return wrapper

        # Play/Pause
        QShortcut(QKeySequence("Space"), window).activated.connect(
            _do("play_pause", lambda: pv.pause() if pv._playing else pv.play()))

        # Tools
        QShortcut(QKeySequence("V"), window).activated.connect(
            _do("select_tool", lambda: (
                tp.canvas.set_tool("select"),
                tp.btn_select.setChecked(True),
                tp.btn_razor.setChecked(False))))
        QShortcut(QKeySequence("C"), window).activated.connect(
            _do("razor_tool", lambda: (
                tp.canvas.set_tool("razor"),
                tp.btn_razor.setChecked(True),
                tp.btn_select.setChecked(False))))

        # Zoom
        QShortcut(QKeySequence("Ctrl+="), window).activated.connect(
            _do("zoom_in", tp._zoom_in))
        QShortcut(QKeySequence("Ctrl+-"), window).activated.connect(
            _do("zoom_out", tp._zoom_out))

        # Navigation
        QShortcut(QKeySequence("J"), window).activated.connect(
            _do("skip_back", pv._skip_back))
        QShortcut(QKeySequence("L"), window).activated.connect(
            _do("skip_forward", pv._skip_forward))

        logger.info("Shortcuts registered: Space, V, C, Ctrl+=/-, J, L")

    # Defer until after __init__ completes
    QTimer.singleShot(100, _bind)