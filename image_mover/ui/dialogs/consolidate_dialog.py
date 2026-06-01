from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QHBoxLayout
)

from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile
from image_mover.ui.workers.move_worker import MoveWorker


class ConsolidateDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Consolidate Duplicates")
        self.setMinimumWidth(420)
        self._db = db
        self._worker = None

        layout = QVBoxLayout(self)

        cache = Cache(db) if db is not None else None
        groups = cache.get_duplicates() if cache is not None else []
        files_to_remove = [f for group in groups for f in group.to_remove]
        total_bytes = sum(f.size_bytes for f in files_to_remove)

        layout.addWidget(QLabel(f"Duplicate groups found: {len(groups)}"))
        layout.addWidget(QLabel(f"Files to remove: {len(files_to_remove)}"))
        layout.addWidget(QLabel(f"Space to reclaim: {total_bytes / 1024 / 1024:.1f} MB"))

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)

        self._btn_confirm = QPushButton("Remove duplicates")
        self._btn_confirm.setEnabled(bool(files_to_remove))
        self._btn_confirm.clicked.connect(lambda: self._start(files_to_remove))
        btn_row.addWidget(self._btn_confirm)

        self._btn_done = QPushButton("Done")
        self._btn_done.setVisible(False)
        self._btn_done.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_done)
        layout.addLayout(btn_row)

    def _start(self, files: list[MediaFile]):
        self._btn_confirm.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = MoveWorker(files, destinations={}, db=self._db, mode="consolidate", parent=self)
        self._worker.progress.connect(lambda n, t: (self._progress.setRange(0, t), self._progress.setValue(n)))
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(lambda msg: self._status.setText(msg))
        self._worker.start()

    def _on_done(self, moved: int, errors: int):
        self._status.setText(f"Removed {moved} files. {errors} errors.")
        self._progress.setVisible(False)
        self._worker.deleteLater()
        self._btn_cancel.setVisible(False)
        self._btn_done.setVisible(True)
