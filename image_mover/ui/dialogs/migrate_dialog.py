from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QFileDialog, QHBoxLayout
)

from image_mover.core.cache import Cache
from image_mover.ui.workers.move_worker import MoveWorker


class MigrateDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Migrate Files")
        self.setMinimumWidth(420)
        self._db = db
        self._dest: str | None = None
        self._worker = None

        layout = QVBoxLayout(self)

        self._dest_label = QLabel("No destination selected")
        layout.addWidget(self._dest_label)

        btn_pick = QPushButton("Choose destination…")
        btn_pick.clicked.connect(self._pick_dest)
        layout.addWidget(btn_pick)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_start = QPushButton("Start migration")
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._start)
        btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

    def _pick_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select destination")
        if path:
            self._dest = path
            self._dest_label.setText(path)
            self._btn_start.setEnabled(True)

    def _start(self):
        cache = Cache(self._db) if self._db else None
        all_files = cache.get_all_files() if cache else []
        pending = [f for f in all_files if f.migrated_to is None]

        images = [f for f in pending if f.media_type == "image"]
        videos = [f for f in pending if f.media_type == "video"]
        ordered = images + videos

        self._btn_start.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(ordered))
        self._worker = MoveWorker(ordered, self._dest, self._db, mode="migrate", parent=self)
        self._worker.progress.connect(lambda n, t: self._progress.setValue(n))
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(lambda msg: self._status.setText(msg))
        self._worker.start()

    def _on_done(self, moved: int, errors: int):
        self._status.setText(f"Migrated {moved} files. {errors} errors.")
        self._progress.setVisible(False)
        self._worker.deleteLater()
