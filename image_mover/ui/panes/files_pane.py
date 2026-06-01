from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile


class FilesPane(QWidget):
    file_selected = pyqtSignal(object)  # emits MediaFile

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._files: list[MediaFile] = []
        self._current_source: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("Files"))

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Date", "Type"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._table)

    def set_db(self, db):
        self._db = db

    def load_source(self, source_dir: str):
        if self._db is None or not source_dir:
            return
        self._current_source = source_dir
        cache = Cache(self._db)
        all_files = cache.get_all_files()
        self._files = [f for f in all_files if any(Path(p).is_relative_to(Path(source_dir)) for p in f.paths)]
        self._populate()

    def refresh(self):
        if self._current_source:
            self.load_source(self._current_source)

    def _populate(self):
        self._table.setRowCount(0)
        for f in self._files:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name = f.paths[0].split("/")[-1]
            date_str = f.canonical_date.strftime("%Y-%m-%d") if f.canonical_date else "—"
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(date_str))
            type_text = f"{f.media_type} [DUP]" if f.is_duplicate else f.media_type
            type_item = QTableWidgetItem(type_text)
            self._table.setItem(row, 2, type_item)
            if f.is_duplicate:
                for col in range(3):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(QColor(80, 40, 40))

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self._files):
            self.file_selected.emit(self._files[row])
