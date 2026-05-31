from __future__ import annotations
import shutil
from pathlib import Path
from image_mover.core.models import MediaFile


class Organizer:
    def __init__(self, destination: Path):
        self._dest = Path(destination)

    def move(self, f: MediaFile) -> str:
        src = Path(f.primary_path)
        if not src.exists():
            raise FileNotFoundError(str(src))

        date = f.canonical_date
        target_dir = self._dest / f"{date.year:04d}" / f"{date.month:02d}" / f"{date.day:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        dest = target_dir / src.name
        dest = self._resolve_collision(dest, src)

        shutil.move(str(src), str(dest))
        return str(dest)

    def _resolve_collision(self, dest: Path, src: Path) -> Path:
        if not dest.exists() or dest.samefile(src):
            return dest
        stem, suffix = dest.stem, dest.suffix
        counter = 1
        while True:
            candidate = dest.parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
