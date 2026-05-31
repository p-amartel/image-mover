from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MediaFile:
    hash: str
    paths: list[str]
    media_type: str  # "image" | "video"
    size_bytes: int
    exif_date: datetime | None
    file_date: datetime
    extension: str
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    migrated_to: str | None = None

    @property
    def canonical_date(self) -> datetime:
        return self.exif_date if self.exif_date is not None else self.file_date

    @property
    def is_duplicate(self) -> bool:
        return len(self.paths) > 1

    @property
    def primary_path(self) -> str:
        return self.paths[0]


@dataclass
class DuplicateGroup:
    hash: str
    files: list[MediaFile]

    @property
    def keeper(self) -> MediaFile:
        return min(self.files, key=lambda f: f.canonical_date)

    @property
    def to_remove(self) -> list[MediaFile]:
        return [f for f in self.files if f is not self.keeper]

    @property
    def paths(self) -> list[str]:
        return [p for f in self.files for p in f.paths]


@dataclass
class ScanSession:
    session_id: str
    source_dir: str
    started_at: datetime
    completed_at: datetime | None = None
    files_scanned: int = 0
    files_new: int = 0
    duplicates_found: int = 0
