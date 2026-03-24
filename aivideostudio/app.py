from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from aivideostudio.config import Config
from aivideostudio.gui.main_window import MainWindow

def create_app(argv):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("AIVideoStudio")
    app.setOrganizationName("AVS")
    qss = Path(__file__).parent / "gui" / "styles" / "dark_theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    config = Config()
    window = MainWindow(config)
    return app, window