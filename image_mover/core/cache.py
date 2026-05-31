from __future__ import annotations
from datetime import datetime, UTC
from image_mover.core.models import MediaFile, DuplicateGroup


def _dt(val: str | None) -> datetime | None:
    """Parse ISO format datetime string, returning None if val is None."""
    return datetime.fromisoformat(val) if val else None


class Cache:
    def __init__(self, db):
        self._files = db["files"]
        self._sessions = db["scan_sessions"]
        self._files.create_index("paths")

    def upsert_file(self, f: MediaFile) -> None:
        existing = self._files.find_one({"_id": f.hash})
        if existing:
            merged_paths = list(set(existing["paths"]) | set(f.paths))
            merged_dates = {**existing.get("path_dates", {}), **{p: f.file_date.isoformat() for p in f.paths}}
            self._files.update_one(
                {"_id": f.hash},
                {"$set": {"paths": merged_paths, "path_dates": merged_dates, "last_seen": datetime.now(UTC).isoformat()}},
            )
        else:
            doc = {
                "_id": f.hash,
                "paths": f.paths,
                "path_dates": {p: f.file_date.isoformat() for p in f.paths},
                "media_type": f.media_type,
                "size_bytes": f.size_bytes,
                "exif_date": f.exif_date.isoformat() if f.exif_date else None,
                "file_date": f.file_date.isoformat(),
                "canonical_date": f.canonical_date.isoformat(),
                "extension": f.extension,
                "last_seen": datetime.now(UTC).isoformat(),
                "migrated_to": None,
            }
            self._files.insert_one(doc)

    def get_file_by_hash(self, hash: str) -> MediaFile | None:
        doc = self._files.find_one({"_id": hash})
        return self._doc_to_media_file(doc) if doc else None

    def get_duplicates(self) -> list[DuplicateGroup]:
        groups = []
        for doc in self._files.find():
            if len(doc.get("paths", [])) <= 1:
                continue
            path_dates = doc.get("path_dates", {})
            members = []
            for p in doc["paths"]:
                fd_str = path_dates.get(p, doc["file_date"])
                mf = MediaFile(
                    hash=doc["_id"],
                    paths=[p],
                    media_type=doc["media_type"],
                    size_bytes=doc["size_bytes"],
                    exif_date=_dt(doc.get("exif_date")),
                    file_date=_dt(fd_str),
                    extension=doc["extension"],
                    migrated_to=doc.get("migrated_to"),
                )
                members.append(mf)
            groups.append(DuplicateGroup(hash=doc["_id"], files=members))
        return groups

    def mark_migrated(self, hash: str, dest_path: str) -> None:
        self._files.update_one(
            {"_id": hash},
            {"$set": {"migrated_to": dest_path, "paths": [dest_path]}},
        )

    def remove_path(self, hash: str, path: str) -> None:
        doc = self._files.find_one({"_id": hash})
        if not doc:
            return
        new_paths = [p for p in doc["paths"] if p != path]
        if new_paths:
            self._files.update_one({"_id": hash}, {"$set": {"paths": new_paths}})
        else:
            self._files.delete_one({"_id": hash})

    def is_cached(self, path: str, size_bytes: int) -> bool:
        doc = self._files.find_one({"paths": path})
        if not doc:
            return False
        return doc.get("size_bytes") == size_bytes

    def get_all_files(self) -> list[MediaFile]:
        return [self._doc_to_media_file(doc) for doc in self._files.find()]

    def clear(self) -> None:
        self._files.drop()
        self._sessions.drop()

    def _doc_to_media_file(self, doc: dict) -> MediaFile:
        return MediaFile(
            hash=doc["_id"],
            paths=doc["paths"],
            media_type=doc["media_type"],
            size_bytes=doc["size_bytes"],
            exif_date=_dt(doc.get("exif_date")),
            file_date=_dt(doc["file_date"]),
            extension=doc["extension"],
            migrated_to=doc.get("migrated_to"),
        )
