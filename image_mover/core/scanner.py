from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path

import exifread

from image_mover.core.models import MediaFile
from image_mover.core.hasher import hash_file

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".bmp",
              ".tiff", ".tif", ".webp", ".cr2", ".cr3", ".nef", ".arw",
              ".dng", ".orf", ".rw2", ".pef"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts",
              ".m2ts", ".3gp", ".wmv"}


class Scanner:
    def __init__(self, allowed_extensions: set[str], cache=None):
        self._exts = {e.lower() for e in allowed_extensions}
        self._cache = cache

    def iter_files(self, directory: Path):
        for root, _dirs, files in os.walk(directory):
            for name in files:
                path = Path(root) / name
                ext = path.suffix.lower()
                if ext not in self._exts:
                    continue
                try:
                    yield self._build_media_file(path, ext)
                except (PermissionError, OSError):
                    continue

    def _build_media_file(self, path: Path, ext: str) -> MediaFile:
        st = path.stat()
        size = st.st_size
        mtime = st.st_mtime
        birth = getattr(st, "st_birthtime", 0.0)
        file_date = datetime.fromtimestamp(birth if birth else mtime)
        media_type = "image" if ext in IMAGE_EXTS else "video"

        if self._cache and self._cache.is_cached(str(path), size):
            cached = self._cache.get_file_by_path(str(path))
            if cached:
                return cached

        file_hash = hash_file(path)
        exif_date = _extract_exif_date(path) if media_type == "image" else None

        return MediaFile(
            hash=file_hash,
            paths=[str(path)],
            media_type=media_type,
            size_bytes=size,
            exif_date=exif_date,
            file_date=file_date,
            extension=ext,
        )


def _extract_exif_date(path: Path) -> datetime | None:
    try:
        with open(path, "rb") as fh:
            tags = exifread.process_file(fh, stop_tag="EXIF DateTimeOriginal", details=False)
        tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        if not tag:
            return None
        return datetime.strptime(str(tag.values), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
