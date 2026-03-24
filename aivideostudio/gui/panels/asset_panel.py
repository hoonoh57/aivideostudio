from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QLabel, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QSize, QMimeData, QPoint
from PySide6.QtGui import QIcon, QPixmap, QDrag
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




class DraggableListWidget(QListWidget):
    """QListWidget that supports dragging file paths to timeline."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self._drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start_pos is None:
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < 20:
            return
        item = self.currentItem()
        if item is None:
            return
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(file_path)
        mime.setData("application/x-aivideo-asset", file_path.encode("utf-8"))
        drag.setMimeData(mime)
        # Optional: set drag pixmap from icon
        icon = item.icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(QSize(80, 45)))
        drag.exec(Qt.DropAction.CopyAction)


class AssetPanel(QWidget):
    file_imported = Signal(str)
    file_double_clicked = Signal(str)

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

        self.list_widget = DraggableListWidget()
        self.list_widget.setIconSize(QSize(80, 45))
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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