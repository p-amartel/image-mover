from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QFileDialog, QHBoxLayout, QFrame
)

from image_mover.core.cache import Cache
from image_mover.ui.workers.move_worker import MoveWorker


class MigrateDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Migrate Files")
        self.setMinimumWidth(460)
        self._db = db
        self._img_dest: str | None = None
        self._vid_dest: str | None = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Images destination
        layout.addWidget(QLabel("Images destination:"))
        img_row = QHBoxLayout()
        self._img_label = QLabel("Not selected")
        self._img_label.setStyleSheet("color: grey;")
        img_row.addWidget(self._img_label, stretch=1)
        btn_img = QPushButton("Choose…")
        btn_img.clicked.connect(self._pick_img_dest)
        img_row.addWidget(btn_img)
        layout.addLayout(img_row)

        # Videos destination
        layout.addWidget(QLabel("Videos destination:"))
        vid_row = QHBoxLayout()
        self._vid_label = QLabel("Not selected")
        self._vid_label.setStyleSheet("color: grey;")
        vid_row.addWidget(self._vid_label, stretch=1)
        btn_vid = QPushButton("Choose…")
        btn_vid.clicked.connect(self._pick_vid_dest)
        vid_row.addWidget(btn_vid)
        layout.addLayout(vid_row)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

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

    def _pick_img_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select images destination")
        if path:
            self._img_dest = path
            self._img_label.setText(path)
            self._img_label.setStyleSheet("")
            self._update_start_button()

    def _pick_vid_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select videos destination")
        if path:
            self._vid_dest = path
            self._vid_label.setText(path)
            self._vid_label.setStyleSheet("")
            self._update_start_button()

    def _update_start_button(self):
        self._btn_start.setEnabled(
            self._img_dest is not None and self._vid_dest is not None
        )

    def _start(self):
        cache = Cache(self._db) if self._db is not None else None
        all_files = cache.get_all_files() if cache is not None else []
        pending = [f for f in all_files if f.migrated_to is None]

        images = [f for f in pending if f.media_type == "image"]
        videos = [f for f in pending if f.media_type == "video"]
        ordered = images + videos

        self._btn_start.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(ordered))

        destinations = {"image": self._img_dest, "video": self._vid_dest}
        self._worker = MoveWorker(ordered, destinations, self._db, mode="migrate", parent=self)
        self._worker.progress.connect(lambda n, t: self._progress.setValue(n))
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(lambda msg: self._status.setText(msg))
        self._worker.start()

    def _on_done(self, moved: int, errors: int):
        self._status.setText(f"Migrated {moved} files. {errors} errors.")
        self._progress.setVisible(False)
        self._worker.deleteLater()
