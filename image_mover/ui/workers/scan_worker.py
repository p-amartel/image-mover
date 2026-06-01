from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from image_mover.core.scanner import Scanner, IMAGE_EXTS, VIDEO_EXTS
from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile

ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


class ScanWorker(QThread):
    progress = pyqtSignal(int, int)       # (current, total)
    file_found = pyqtSignal(object)       # MediaFile
    finished = pyqtSignal(int, int, int)  # (scanned, new, dupes)
    error = pyqtSignal(str)

    def __init__(self, source_dir: str, db, parent=None):
        super().__init__(parent)
        self._dir = Path(source_dir)
        self._db = db

    def run(self):
        try:
            cache = Cache(self._db)
            scanner = Scanner(allowed_extensions=ALL_EXTS, cache=cache)
            files = list(scanner.iter_files(self._dir))
            total = len(files)
            new_count = 0
            for i, f in enumerate(files, 1):
                existing = cache.get_file_by_hash(f.hash)
                if existing is None:
                    new_count += 1
                cache.upsert_file(f)
                self.file_found.emit(f)
                self.progress.emit(i, total)
            dupes = len(cache.get_duplicates())
            self.finished.emit(total, new_count, dupes)
        except Exception as e:
            self.error.emit(str(e))
