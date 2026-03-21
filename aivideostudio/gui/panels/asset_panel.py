from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QLabel, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap
from loguru import logger

SUPPORTED = {
    "video": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"],
    "audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"],
    "image": [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"],
    "subtitle": [".srt", ".ass", ".vtt"],
}
ALL_EXTS = []
for v in SUPPORTED.values():
    ALL_EXTS.extend(v)


class AssetPanel(QWidget):
    file_imported = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        self.btn_import = QPushButton("+ Import")
        self.btn_import.clicked.connect(self._on_import)
        top.addWidget(self.btn_import)

        self.lbl_count = QLabel("0 files")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.lbl_count)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(80, 45))
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setDragEnabled(True)
        self.list_widget.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        self.setAcceptDrops(True)

    def _on_import(self):
        exts = " ".join(f"*{e}" for e in ALL_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Media", "",
            f"Media Files ({exts});;All Files (*.*)"
        )
        for f in files:
            self.add_file(f)

    def add_file(self, file_path):
        p = Path(file_path)
        if not p.exists():
            return
        if p.suffix.lower() not in ALL_EXTS:
            logger.warning(f"Unsupported format: {p.suffix}")
            return

        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == str(p):
                return

        item = QListWidgetItem(p.name)
        item.setData(Qt.ItemDataRole.UserRole, str(p))

        size_mb = p.stat().st_size / (1024 * 1024)
        item.setToolTip(f"{p.name}\n{size_mb:.1f} MB\n{p.suffix.upper()}")

        self.list_widget.addItem(item)
        self.lbl_count.setText(f"{self.list_widget.count()} files")
        self.file_imported.emit(str(p))
        logger.info(f"File added to panel: {p.name}")

    def set_thumbnail(self, file_path, thumb_path):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == file_path:
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    item.setIcon(QIcon(pix))
                break

    def _on_double_click(self, index):
        item = self.list_widget.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            self.file_double_clicked.emit(path)

    def get_selected_path(self):
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.add_file(path)
