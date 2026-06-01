from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from image_mover.core.scanner import Scanner, IMAGE_EXTS, VIDEO_EXTS
from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile

ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


class ScanWorker(QThread):
    progress = pyqtSignal(int, int)       # (current, total)
    scanning_file = pyqtSignal(str)       # current filename being processed
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

            # Phase 1: fast enumeration (no hashing) to get accurate total
            paths = scanner.list_paths(self._dir)
            total = len(paths)
            new_count = 0

            # Phase 2: process each file — hash + EXIF + cache upsert
            for i, (path, ext) in enumerate(paths, 1):
                self.scanning_file.emit(path.name)
                try:
                    f = scanner.build_media_file(path, ext)
                except (PermissionError, OSError):
                    self.progress.emit(i, total)
                    continue
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
