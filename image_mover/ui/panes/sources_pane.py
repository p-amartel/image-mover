from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget,
    QPushButton, QFileDialog, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt


class SourcesPane(QWidget):
    source_selected = pyqtSignal(str)  # emits directory path

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._sources: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("Sources"))

        self._list = QListWidget()
        self._list.currentTextChanged.connect(self.source_selected)
        layout.addWidget(self._list)

        btn = QPushButton("+ Add source…")
        btn.clicked.connect(self._add_source)
        layout.addWidget(btn)

    def _add_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select source directory")
        if path and path not in self._sources:
            self._sources.append(path)
            self._list.addItem(path)

    def refresh(self):
        current = self._list.currentItem()
        current_text = current.text() if current else None
        self._list.clear()
        for s in self._sources:
            self._list.addItem(s)
        if current_text:
            items = self._list.findItems(current_text, Qt.MatchFlag.MatchExactly)
            if items:
                self._list.setCurrentItem(items[0])
