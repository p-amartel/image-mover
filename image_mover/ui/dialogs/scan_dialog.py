from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QFileDialog, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal

from image_mover.ui.workers.scan_worker import ScanWorker


class ScanDialog(QDialog):
    scan_complete = pyqtSignal(str)  # emits source_dir path

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan Directory")
        self.setMinimumWidth(420)
        self._db = db
        self._worker = None
        self._selected_dir: str | None = None

        layout = QVBoxLayout(self)

        self._dir_label = QLabel("No directory selected")
        layout.addWidget(self._dir_label)

        btn_row = QHBoxLayout()
        btn_pick = QPushButton("Choose directory…")
        btn_pick.clicked.connect(self._pick_dir)
        btn_row.addWidget(btn_pick)
        self._btn_start = QPushButton("Start scan")
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._start_scan)
        btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._file_label = QLabel("")
        self._file_label.setStyleSheet("color: grey; font-size: 11px;")
        self._file_label.setVisible(False)
        layout.addWidget(self._file_label)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self.accept)
        layout.addWidget(self._btn_close)

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select directory to scan")
        if path:
            self._selected_dir = path
            self._dir_label.setText(path)
            self._btn_start.setEnabled(True)

    def _start_scan(self):
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._file_label.setVisible(True)
        self._file_label.setText("Discovering files…")
        self._btn_start.setEnabled(False)
        self._worker = ScanWorker(self._selected_dir, self._db, self)
        self._worker.scanning_file.connect(self._on_scanning_file)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_scanning_file(self, filename: str):
        self._file_label.setText(filename)

    def _on_progress(self, current: int, total: int):
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._status.setText(f"Scanning… {current} / {total}")

    def _on_finished(self, scanned: int, new: int, dupes: int):
        self._status.setText(f"Done: {scanned} files · {new} new · {dupes} duplicate groups")
        self._progress.setVisible(False)
        self._file_label.setVisible(False)
        self._btn_start.setEnabled(True)
        self._worker.deleteLater()
        self.scan_complete.emit(self._selected_dir)

    def _on_error(self, msg: str):
        self._status.setText(f"Error: {msg}")
        self._progress.setVisible(False)
        self._file_label.setVisible(False)
        self._btn_start.setEnabled(True)
        self._worker.deleteLater()
