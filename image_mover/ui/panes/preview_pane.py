from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from image_mover.core.models import MediaFile


class PreviewPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._thumb = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._thumb.setMinimumHeight(200)
        layout.addWidget(self._thumb)

        self._name = QLabel()
        self._name.setWordWrap(True)
        self._size = QLabel()
        self._date = QLabel()
        self._type = QLabel()
        self._dupe = QLabel()
        self._dupe.setStyleSheet("color: #e07070;")

        for lbl in (self._name, self._size, self._date, self._type, self._dupe):
            layout.addWidget(lbl)
        layout.addStretch()

    def show_file(self, f: MediaFile):
        path = Path(f.primary_path)
        self._name.setText(path.name)
        self._size.setText(f"{f.size_bytes / 1024:.1f} KB")
        self._date.setText(f.canonical_date.strftime("%Y-%m-%d %H:%M") if f.canonical_date else "—")
        self._type.setText(f.media_type)
        self._dupe.setText(f"⚠ Duplicate ({len(f.paths)} copies)" if f.is_duplicate else "")

        if f.media_type == "image" and path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._thumb.setPixmap(
                    pix.scaled(300, 250, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
                return
        self._thumb.setText("(no preview)")
