"""Toolbar with icons — benchmarked from DaVinci Resolve / Premiere Pro style."""
from PyQt6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtCore import Qt, QSize


def create_toolbar(window):
    tb = QToolBar("Tools", window)
    tb.setObjectName("main_toolbar")
    tb.setMovable(False)
    tb.setIconSize(QSize(20, 20))
    tb.setStyleSheet(
        "QToolBar{background:#1e1e1e;border:none;spacing:2px;padding:2px;}"
        "QToolButton{color:#ddd;padding:4px 8px;border-radius:3px;font-size:12px;}"
        "QToolButton:hover{background:#3a3a3a;}"
        "QToolButton:checked{background:#2979ff;color:white;}"
        "QToolButton:pressed{background:#1565c0;}")

    tools = [
        ("\U0001F5B1 Select",  "select",   "V", "Selection tool (V)"),
        ("\u2702 Razor",   "razor",    "C", "Razor / Split tool (C)"),
        (None, None, None, None),  # separator
        ("\U0001F50D+ Zoom In",  "zoom_in",  "=", "Zoom In (=)"),
        ("\U0001F50D\u2013 Zoom Out", "zoom_out", "-", "Zoom Out (-)"),
        (None, None, None, None),  # separator
        ("\U0001F5D1 Delete", "delete",   "Del", "Delete selected (Del)"),
        ("\u21A9 Undo",   "undo",     "Ctrl+Z", "Undo (Ctrl+Z)"),
        ("\u21AA Redo",   "redo",     "Ctrl+Y", "Redo (Ctrl+Y)"),
        (None, None, None, None),  # separator
        ("\U0001F4C2 Import", "import",   "Ctrl+I", "Import media"),
        ("\U0001F4E4 Export", "export",   "Ctrl+E", "Export timeline"),
    ]

    for label, action_id, shortcut, tooltip in tools:
        if label is None:
            tb.addSeparator()
            continue
        btn = QToolButton()
        btn.setText(label)
        btn.setToolTip(f"{tooltip} [{shortcut}]" if shortcut else tooltip)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        if action_id in ("select", "razor"):
            btn.setCheckable(True)
            if action_id == "select":
                btn.setChecked(True)
                window._tb_select = btn
            else:
                window._tb_razor = btn
        window._toolbar_buttons = getattr(window, '_toolbar_buttons', {})
        window._toolbar_buttons[action_id] = btn
        tb.addWidget(btn)

    # Connect toolbar buttons to timeline panel tools
    def connect_later():
        """Connect after all panels are set up."""
        btns = getattr(window, '_toolbar_buttons', {})
        tp = getattr(window, 'timeline_panel', None)
        preview = getattr(window, 'preview', None)
        asset = getattr(window, 'asset_panel', None)

        if tp:
            if 'select' in btns:
                btns['select'].clicked.connect(lambda: (
                    tp.canvas.set_tool('select'),
                    btns['select'].setChecked(True),
                    btns.get('razor', QToolButton()).setChecked(False)))
            if 'razor' in btns:
                btns['razor'].clicked.connect(lambda: (
                    tp.canvas.set_tool('razor'),
                    btns['razor'].setChecked(True),
                    btns.get('select', QToolButton()).setChecked(False)))
            if 'zoom_in' in btns:
                btns['zoom_in'].clicked.connect(tp._zoom_in)
            if 'zoom_out' in btns:
                btns['zoom_out'].clicked.connect(tp._zoom_out)
            if 'delete' in btns:
                btns['delete'].clicked.connect(tp._delete_clip)
            if 'undo' in btns:
                btns['undo'].clicked.connect(tp._do_undo)
            if 'redo' in btns:
                btns['redo'].clicked.connect(tp._do_redo)
        if asset and 'import' in btns:
            btns['import'].clicked.connect(asset._on_import)

    # Defer connection until after __init__
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(100, connect_later)

    window.addToolBar(tb)
    return tb
