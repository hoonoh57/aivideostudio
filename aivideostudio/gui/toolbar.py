from PyQt6.QtWidgets import QToolBar
from PyQt6.QtGui import QAction

def create_toolbar(window):
    tb = QToolBar("Tools", window)
    tb.setObjectName("main_toolbar")
    for label in ["Select", "Razor", "Text", "Play", "Import", "Export"]:
        tb.addAction(QAction(label, window))
    window.addToolBar(tb)
