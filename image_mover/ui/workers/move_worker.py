from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from image_mover.core.organizer import Organizer
from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile


class MoveWorker(QThread):
    progress = pyqtSignal(int, int)   # (current, total)
    finished = pyqtSignal(int, int)   # (moved, errors)
    error_occurred = pyqtSignal(str)  # per-file error

    def __init__(self, files: list[MediaFile], destination: str, db, mode: str, parent=None):
        super().__init__(parent)
        self._files = files
        self._dest = destination
        self._db = db
        self._mode = mode  # "migrate" | "consolidate"

    def run(self):
        cache = Cache(self._db)
        org = Organizer(Path(self._dest))
        total = len(self._files)
        moved, errors = 0, 0
        for i, f in enumerate(self._files, 1):
            try:
                if self._mode == "migrate":
                    new_path = org.move(f)
                    cache.mark_migrated(f.hash, new_path)
                elif self._mode == "consolidate":
                    import os
                    os.remove(f.primary_path)
                    cache.remove_path(f.hash, f.primary_path)
                moved += 1
            except Exception as e:
                errors += 1
                self.error_occurred.emit(f"{f.primary_path}: {e}")
            self.progress.emit(i, total)
        self.finished.emit(moved, errors)
