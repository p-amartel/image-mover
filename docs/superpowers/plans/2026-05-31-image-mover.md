# image-mover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS PyQt6 desktop app that scans directories for images/videos, deduplicates by SHA-256 hash, and migrates files into YYYY/MM/DD folder structure with MongoDB as persistent cache.

**Architecture:** Layered — pure Python `core/` library (scanner, hasher, deduplicator, organizer, cache) with PyQt6 as a thin UI layer. Background work runs in QThread workers that emit Qt signals. MongoDB stores file hashes, paths, and scan sessions to avoid re-hashing unchanged files.

**Tech Stack:** Python 3.11+, PyQt6, pymongo, exifread, pymediainfo, pytest

---

## File Map

```
image_mover/
  __init__.py
  core/
    __init__.py
    models.py          # MediaFile, ScanSession, DuplicateGroup dataclasses
    cache.py           # MongoDB read/write
    hasher.py          # streaming SHA-256
    scanner.py         # walk dirs, extract metadata, call hasher
    deduplicator.py    # group by hash, pick oldest keeper
    organizer.py       # move files into dest/YYYY/MM/DD/
  ui/
    __init__.py
    app.py             # QApplication entry point
    main_window.py     # three-pane shell + toolbar + status bar
    panes/
      __init__.py
      sources_pane.py  # left pane: source directory list
      files_pane.py    # center pane: file list with DUP badges
      preview_pane.py  # right pane: thumbnail + metadata
    dialogs/
      __init__.py
      scan_dialog.py        # progress dialog during scan
      consolidate_dialog.py # summary + confirm before dedup
      migrate_dialog.py     # destination picker + progress
      settings_dialog.py    # clear cache button
    workers/
      __init__.py
      scan_worker.py   # QThread: runs scanner+hasher, emits signals
      move_worker.py   # QThread: runs organizer/dedup deletions, emits signals
tests/
  conftest.py          # shared fixtures: tmp_dir, mongo test db
  core/
    test_hasher.py
    test_scanner.py
    test_deduplicator.py
    test_organizer.py
    test_cache.py
  workers/
    test_scan_worker.py
    test_move_worker.py
pyproject.toml
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `image_mover/__init__.py`
- Create: `image_mover/core/__init__.py`
- Create: `image_mover/ui/__init__.py`
- Create: `image_mover/ui/panes/__init__.py`
- Create: `image_mover/ui/dialogs/__init__.py`
- Create: `image_mover/ui/workers/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "image-mover"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "PyQt6>=6.6",
    "pymongo>=4.6",
    "exifread>=3.0",
    "pymediainfo>=6.1",
]

[project.scripts]
image-mover = "image_mover.ui.app:main"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt>=4.4", "mongomock>=4.1"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create all empty `__init__.py` files**

```bash
mkdir -p image_mover/core image_mover/ui/panes image_mover/ui/dialogs image_mover/ui/workers tests/core tests/workers
touch image_mover/__init__.py image_mover/core/__init__.py
touch image_mover/ui/__init__.py image_mover/ui/panes/__init__.py
touch image_mover/ui/dialogs/__init__.py image_mover/ui/workers/__init__.py
touch tests/__init__.py tests/core/__init__.py tests/workers/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: no errors, `image-mover` command available.

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
import mongomock
from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def mongo_client():
    client = mongomock.MongoClient()
    yield client
    client.close()


@pytest.fixture
def db(mongo_client):
    return mongo_client["image_mover_test"]
```

- [ ] **Step 5: Verify pytest runs**

```bash
pytest --collect-only
```

Expected: "no tests ran" with 0 errors.

- [ ] **Step 6: Commit**

```bash
git init
git add pyproject.toml image_mover/ tests/
git commit -m "feat: project scaffold"
```

---

## Task 2: Core models

**Files:**
- Create: `image_mover/core/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_models.py
from datetime import datetime
from image_mover.core.models import MediaFile, DuplicateGroup


def test_media_file_is_image():
    f = MediaFile(
        hash="abc123",
        paths=["/Photos/a.jpg"],
        media_type="image",
        size_bytes=1024,
        exif_date=datetime(2021, 6, 12, 14, 32),
        file_date=datetime(2021, 6, 12, 14, 32),
        extension=".jpg",
    )
    assert f.canonical_date == datetime(2021, 6, 12, 14, 32)
    assert f.is_duplicate is False


def test_media_file_canonical_date_falls_back_to_file_date():
    f = MediaFile(
        hash="abc123",
        paths=["/Photos/a.jpg"],
        media_type="image",
        size_bytes=1024,
        exif_date=None,
        file_date=datetime(2021, 6, 12),
        extension=".jpg",
    )
    assert f.canonical_date == datetime(2021, 6, 12)


def test_duplicate_group_keeper_is_oldest():
    files = [
        MediaFile("h1", ["/a.jpg"], "image", 1024, datetime(2023, 1, 1), datetime(2023, 1, 1), ".jpg"),
        MediaFile("h1", ["/b.jpg"], "image", 1024, datetime(2021, 6, 12), datetime(2021, 6, 12), ".jpg"),
    ]
    group = DuplicateGroup(hash="h1", files=files)
    assert group.keeper.exif_date == datetime(2021, 6, 12)
    assert len(group.to_remove) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'image_mover.core.models'`

- [ ] **Step 3: Implement models.py**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MediaFile:
    hash: str
    paths: list[str]
    media_type: str  # "image" | "video"
    size_bytes: int
    exif_date: datetime | None
    file_date: datetime
    extension: str
    last_seen: datetime = field(default_factory=datetime.utcnow)
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


@dataclass
class ScanSession:
    session_id: str
    source_dir: str
    started_at: datetime
    completed_at: datetime | None = None
    files_scanned: int = 0
    files_new: int = 0
    duplicates_found: int = 0
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/models.py tests/core/test_models.py
git commit -m "feat: core data models"
```

---

## Task 3: Cache module (MongoDB)

**Files:**
- Create: `image_mover/core/cache.py`
- Create: `tests/core/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_cache.py
from datetime import datetime
from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile


def make_file(hash="abc", path="/a.jpg", exif=None, fdate=None):
    return MediaFile(
        hash=hash,
        paths=[path],
        media_type="image",
        size_bytes=1024,
        exif_date=exif,
        file_date=fdate or datetime(2021, 1, 1),
        extension=".jpg",
    )


def test_upsert_and_get(db):
    cache = Cache(db)
    f = make_file()
    cache.upsert_file(f)
    result = cache.get_file_by_hash("abc")
    assert result is not None
    assert result.hash == "abc"
    assert "/a.jpg" in result.paths


def test_upsert_adds_new_path_to_existing(db):
    cache = Cache(db)
    cache.upsert_file(make_file(path="/a.jpg"))
    cache.upsert_file(make_file(path="/b.jpg"))
    result = cache.get_file_by_hash("abc")
    assert set(result.paths) == {"/a.jpg", "/b.jpg"}


def test_get_duplicates(db):
    cache = Cache(db)
    f = make_file()
    f.paths = ["/a.jpg", "/b.jpg"]
    cache.upsert_file(f)
    dupes = cache.get_duplicates()
    assert len(dupes) == 1
    assert len(dupes[0].paths) == 2


def test_mark_migrated(db):
    cache = Cache(db)
    cache.upsert_file(make_file())
    cache.mark_migrated("abc", "/dest/2021/01/01/a.jpg")
    result = cache.get_file_by_hash("abc")
    assert result.migrated_to == "/dest/2021/01/01/a.jpg"


def test_clear(db):
    cache = Cache(db)
    cache.upsert_file(make_file())
    cache.clear()
    assert cache.get_file_by_hash("abc") is None


def test_is_cached_unchanged(db):
    cache = Cache(db)
    cache.upsert_file(make_file())
    assert cache.is_cached("/a.jpg", size_bytes=1024, mtime=0.0) is True
    assert cache.is_cached("/a.jpg", size_bytes=9999, mtime=0.0) is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/core/test_cache.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement cache.py**

```python
from __future__ import annotations
from datetime import datetime
from image_mover.core.models import MediaFile, DuplicateGroup


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
                {"$set": {"paths": merged_paths, "path_dates": merged_dates, "last_seen": datetime.utcnow().isoformat()}},
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
                "last_seen": datetime.utcnow().isoformat(),
                "migrated_to": None,
                "mtime": getattr(f, "_mtime", 0.0),
            }
            self._files.insert_one(doc)

    def get_file_by_hash(self, hash: str) -> MediaFile | None:
        doc = self._files.find_one({"_id": hash})
        return self._doc_to_media_file(doc) if doc else None

    def get_duplicates(self) -> list["DuplicateGroup"]:
        from image_mover.core.models import DuplicateGroup
        groups = []
        for doc in self._files.find():
            if len(doc.get("paths", [])) <= 1:
                continue
            path_dates = doc.get("path_dates", {})
            members = []
            for p in doc["paths"]:
                def _dt(val):
                    return datetime.fromisoformat(val) if val else None
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

    def is_cached(self, path: str, size_bytes: int, mtime: float) -> bool:
        doc = self._files.find_one({"paths": path})
        if not doc:
            return False
        return doc.get("size_bytes") == size_bytes

    def clear(self) -> None:
        self._files.drop()
        self._sessions.drop()

    def _doc_to_media_file(self, doc: dict) -> MediaFile:
        def _dt(val):
            return datetime.fromisoformat(val) if val else None

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_cache.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/cache.py tests/core/test_cache.py
git commit -m "feat: MongoDB cache module"
```

---

## Task 4: Hasher

**Files:**
- Create: `image_mover/core/hasher.py`
- Create: `tests/core/test_hasher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/core/test_hasher.py
import hashlib
from pathlib import Path
from image_mover.core.hasher import hash_file


def test_hash_known_content(tmp_dir):
    f = tmp_dir / "test.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert hash_file(f) == expected


def test_hash_large_file_streaming(tmp_dir):
    f = tmp_dir / "big.bin"
    data = b"x" * (200 * 1024)  # 200 KB, crosses chunk boundary
    f.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert hash_file(f) == expected


def test_hash_missing_file_raises(tmp_dir):
    import pytest
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_dir / "nonexistent.jpg")
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/core/test_hasher.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement hasher.py**

```python
import hashlib
from pathlib import Path

CHUNK_SIZE = 64 * 1024  # 64 KB


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_hasher.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/hasher.py tests/core/test_hasher.py
git commit -m "feat: streaming SHA-256 hasher"
```

---

## Task 5: Scanner

**Files:**
- Create: `image_mover/core/scanner.py`
- Create: `tests/core/test_scanner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_scanner.py
from pathlib import Path
from datetime import datetime
from image_mover.core.scanner import Scanner
from image_mover.core.models import MediaFile

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".bmp",
              ".tiff", ".tif", ".webp", ".cr2", ".cr3", ".nef", ".arw",
              ".dng", ".orf", ".rw2", ".pef"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts",
              ".m2ts", ".3gp", ".wmv"}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


def write_fake_jpeg(path: Path):
    # Minimal JFIF header so exifread doesn't crash
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)


def test_scanner_finds_images(tmp_dir):
    (tmp_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    (tmp_dir / "b.txt").write_text("not a media file")
    scanner = Scanner(allowed_extensions=ALL_EXTS)
    files = list(scanner.iter_files(tmp_dir))
    assert len(files) == 1
    assert files[0].extension == ".jpg"
    assert files[0].media_type == "image"


def test_scanner_finds_videos(tmp_dir):
    (tmp_dir / "clip.mp4").write_bytes(b"\x00" * 64)
    scanner = Scanner(allowed_extensions=ALL_EXTS)
    files = list(scanner.iter_files(tmp_dir))
    assert len(files) == 1
    assert files[0].media_type == "video"


def test_scanner_recurses_subdirs(tmp_dir):
    sub = tmp_dir / "sub"
    sub.mkdir()
    (sub / "c.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    scanner = Scanner(allowed_extensions=ALL_EXTS)
    files = list(scanner.iter_files(tmp_dir))
    assert len(files) == 1


def test_scanner_skips_unsupported(tmp_dir):
    (tmp_dir / "doc.pdf").write_bytes(b"%PDF")
    scanner = Scanner(allowed_extensions=ALL_EXTS)
    files = list(scanner.iter_files(tmp_dir))
    assert files == []


def test_scanner_file_date_fallback(tmp_dir):
    p = tmp_dir / "a.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    scanner = Scanner(allowed_extensions=ALL_EXTS)
    files = list(scanner.iter_files(tmp_dir))
    assert isinstance(files[0].file_date, datetime)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/core/test_scanner.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement scanner.py**

```python
from __future__ import annotations
import os
import stat
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

        if self._cache and self._cache.is_cached(str(path), size, mtime):
            cached = self._cache.get_file_by_hash_for_path(str(path))
            if cached:
                return cached

        file_hash = hash_file(path)
        exif_date = _extract_exif_date(path) if media_type == "image" else None

        f = MediaFile(
            hash=file_hash,
            paths=[str(path)],
            media_type=media_type,
            size_bytes=size,
            exif_date=exif_date,
            file_date=file_date,
            extension=ext,
        )
        f._mtime = mtime
        return f


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_scanner.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/scanner.py tests/core/test_scanner.py
git commit -m "feat: directory scanner with EXIF date extraction"
```

---

## Task 6: Deduplicator

**Files:**
- Create: `image_mover/core/deduplicator.py`
- Create: `tests/core/test_deduplicator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_deduplicator.py
from datetime import datetime
from image_mover.core.models import MediaFile
from image_mover.core.deduplicator import build_duplicate_groups


def mf(hash, path, year):
    return MediaFile(hash, [path], "image", 1024,
                     datetime(year, 1, 1), datetime(year, 1, 1), ".jpg")


def test_no_duplicates():
    files = [mf("a", "/a.jpg", 2021), mf("b", "/b.jpg", 2022)]
    groups = build_duplicate_groups(files)
    assert groups == []


def test_single_duplicate_group():
    files = [mf("same", "/a.jpg", 2023), mf("same", "/b.jpg", 2021)]
    groups = build_duplicate_groups(files)
    assert len(groups) == 1
    assert groups[0].keeper.paths == ["/b.jpg"]  # 2021 is older
    assert len(groups[0].to_remove) == 1


def test_multiple_groups():
    files = [
        mf("x", "/x1.jpg", 2022), mf("x", "/x2.jpg", 2020),
        mf("y", "/y1.jpg", 2019), mf("y", "/y2.jpg", 2021),
    ]
    groups = build_duplicate_groups(files)
    assert len(groups) == 2
    keepers = {g.keeper.paths[0] for g in groups}
    assert keepers == {"/x2.jpg", "/y1.jpg"}
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/core/test_deduplicator.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement deduplicator.py**

```python
from __future__ import annotations
from collections import defaultdict
from image_mover.core.models import MediaFile, DuplicateGroup


def build_duplicate_groups(files: list[MediaFile]) -> list[DuplicateGroup]:
    by_hash: dict[str, list[MediaFile]] = defaultdict(list)
    for f in files:
        by_hash[f.hash].append(f)
    return [
        DuplicateGroup(hash=h, files=group)
        for h, group in by_hash.items()
        if len(group) > 1
    ]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_deduplicator.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/deduplicator.py tests/core/test_deduplicator.py
git commit -m "feat: duplicate group detection"
```

---

## Task 7: Organizer

**Files:**
- Create: `image_mover/core/organizer.py`
- Create: `tests/core/test_organizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_organizer.py
import shutil
from datetime import datetime
from pathlib import Path
from image_mover.core.models import MediaFile
from image_mover.core.organizer import Organizer


def make_file(tmp_dir, name="img.jpg", year=2021, month=6, day=12):
    src = tmp_dir / "src" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
    return MediaFile(
        hash="abc",
        paths=[str(src)],
        media_type="image",
        size_bytes=src.stat().st_size,
        exif_date=datetime(year, month, day),
        file_date=datetime(year, month, day),
        extension=".jpg",
    )


def test_organizer_moves_to_yyyy_mm_dd(tmp_dir):
    dest = tmp_dir / "dest"
    f = make_file(tmp_dir)
    org = Organizer(dest)
    new_path = org.move(f)
    assert new_path == str(dest / "2021" / "06" / "12" / "img.jpg")
    assert Path(new_path).exists()


def test_organizer_handles_collision(tmp_dir):
    dest = tmp_dir / "dest"
    f1 = make_file(tmp_dir, "img.jpg")
    f2 = make_file(tmp_dir, "img.jpg")
    # create a second source file with same name
    src2 = tmp_dir / "src2" / "img.jpg"
    src2.parent.mkdir(parents=True, exist_ok=True)
    src2.write_bytes(b"\xff\xd8\xff\xe0" + b"\x01" * 50)
    f2.paths = [str(src2)]
    org = Organizer(dest)
    p1 = org.move(f1)
    p2 = org.move(f2)
    assert p1 != p2
    assert "_1" in Path(p2).name


def test_organizer_missing_source_raises(tmp_dir):
    import pytest
    dest = tmp_dir / "dest"
    f = make_file(tmp_dir)
    Path(f.primary_path).unlink()
    org = Organizer(dest)
    with pytest.raises(FileNotFoundError):
        org.move(f)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/core/test_organizer.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement organizer.py**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_organizer.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add image_mover/core/organizer.py tests/core/test_organizer.py
git commit -m "feat: file organizer with YYYY/MM/DD structure"
```

---

## Task 8: QThread workers

**Files:**
- Create: `image_mover/ui/workers/scan_worker.py`
- Create: `image_mover/ui/workers/move_worker.py`
- Create: `tests/workers/test_scan_worker.py`
- Create: `tests/workers/test_move_worker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/workers/test_scan_worker.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from image_mover.core.models import MediaFile
from image_mover.ui.workers.scan_worker import ScanWorker


def make_media_file():
    return MediaFile("h1", ["/a.jpg"], "image", 1024,
                     datetime(2021,1,1), datetime(2021,1,1), ".jpg")


def test_scan_worker_emits_progress(qtbot):
    worker = ScanWorker(source_dir="/tmp", db=MagicMock())
    mock_files = [make_media_file(), make_media_file()]

    with patch("image_mover.ui.workers.scan_worker.Scanner") as MockScanner:
        MockScanner.return_value.iter_files.return_value = iter(mock_files)
        with patch("image_mover.ui.workers.scan_worker.Cache"):
            signals = []
            worker.progress.connect(lambda n, t: signals.append((n, t)))
            worker.run()

    assert len(signals) == 2
    assert signals[-1] == (2, 2)
```

```python
# tests/workers/test_move_worker.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
from image_mover.core.models import MediaFile
from image_mover.ui.workers.move_worker import MoveWorker


def make_file(path="/src/a.jpg"):
    return MediaFile("h1", [path], "image", 1024,
                     datetime(2021,1,1), datetime(2021,1,1), ".jpg")


def test_move_worker_emits_progress(qtbot, tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"\xff\xd8" + b"\x00" * 50)
    files = [make_file(str(src))]
    db = MagicMock()
    worker = MoveWorker(files=files, destination=str(tmp_path / "dest"), db=db, mode="migrate")

    with patch("image_mover.ui.workers.move_worker.Organizer") as MockOrg:
        MockOrg.return_value.move.return_value = "/dest/2021/01/01/a.jpg"
        done = []
        worker.progress.connect(lambda n, t: done.append((n, t)))
        worker.run()

    assert done[-1] == (1, 1)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/workers/ -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement scan_worker.py**

```python
from __future__ import annotations
from pathlib import Path
import pymongo
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
```

- [ ] **Step 4: Implement move_worker.py**

```python
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/workers/ -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add image_mover/ui/workers/ tests/workers/
git commit -m "feat: QThread scan and move workers"
```

---

## Task 9: Main window shell + toolbar

**Files:**
- Create: `image_mover/ui/main_window.py`

- [ ] **Step 1: Implement main_window.py**

```python
from __future__ import annotations
import pymongo
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar,
    QStatusBar, QLabel, QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from image_mover.core.cache import Cache
from image_mover.ui.panes.sources_pane import SourcesPane
from image_mover.ui.panes.files_pane import FilesPane
from image_mover.ui.panes.preview_pane import PreviewPane

MONGO_URI = "mongodb://labpi01.local:27017/"
DB_NAME = "image_mover"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Mover")
        self.resize(1200, 750)

        self._db = self._connect_mongo()
        self._cache = Cache(self._db) if self._db else None

        self._build_toolbar()
        self._build_panes()
        self._build_status_bar()

    def _connect_mongo(self):
        try:
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            client.server_info()
            return client[DB_NAME]
        except Exception:
            QMessageBox.warning(
                self, "MongoDB unavailable",
                "Cannot reach MongoDB. Running without cache — all files will be re-hashed on each scan."
            )
            return None

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_scan = QAction("Scan", self)
        self._act_consolidate = QAction("Consolidate", self)
        self._act_migrate = QAction("Migrate", self)
        self._act_settings = QAction("Settings", self)

        for act in (self._act_scan, self._act_consolidate, self._act_migrate, self._act_settings):
            tb.addAction(act)

        self._act_scan.triggered.connect(self._on_scan)
        self._act_consolidate.triggered.connect(self._on_consolidate)
        self._act_migrate.triggered.connect(self._on_migrate)
        self._act_settings.triggered.connect(self._on_settings)

    def _build_panes(self):
        self._sources = SourcesPane(self._db)
        self._files = FilesPane()
        self._preview = PreviewPane()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sources)
        splitter.addWidget(self._files)
        splitter.addWidget(self._preview)
        splitter.setSizes([220, 400, 380])
        self.setCentralWidget(splitter)

        self._sources.source_selected.connect(self._files.load_source)
        self._files.file_selected.connect(self._preview.show_file)

    def _build_status_bar(self):
        self._status_label = QLabel("Ready")
        sb = QStatusBar()
        sb.addWidget(self._status_label)
        self.setStatusBar(sb)

    def set_status(self, text: str):
        self._status_label.setText(text)

    def _on_scan(self):
        from image_mover.ui.dialogs.scan_dialog import ScanDialog
        dlg = ScanDialog(self._db, self)
        dlg.scan_complete.connect(self._sources.refresh)
        dlg.exec()

    def _on_consolidate(self):
        from image_mover.ui.dialogs.consolidate_dialog import ConsolidateDialog
        dlg = ConsolidateDialog(self._db, self)
        dlg.exec()
        self._files.refresh()

    def _on_migrate(self):
        from image_mover.ui.dialogs.migrate_dialog import MigrateDialog
        dlg = MigrateDialog(self._db, self)
        dlg.exec()
        self._files.refresh()

    def _on_settings(self):
        from image_mover.ui.dialogs.settings_dialog import SettingsDialog
        SettingsDialog(self._db, self).exec()
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/main_window.py
git commit -m "feat: main window shell with toolbar and three-pane layout"
```

---

## Task 10: Sources pane

**Files:**
- Create: `image_mover/ui/panes/sources_pane.py`

- [ ] **Step 1: Implement sources_pane.py**

```python
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QLabel
)
from PyQt6.QtCore import pyqtSignal

from image_mover.core.cache import Cache


class SourcesPane(QWidget):
    source_selected = pyqtSignal(str)  # emits directory path

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._sources: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("Sources"))

        self._list = QListWidget()
        self._list.currentTextChanged.connect(self.source_selected)
        layout.addWidget(self._list)

        btn = QPushButton("+ Add source…")
        btn.clicked.connect(self._add_source)
        layout.addWidget(btn)

    def _add_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select source directory")
        if path and path not in self._sources:
            self._sources.append(path)
            self._list.addItem(path)

    def refresh(self):
        current = self._list.currentItem()
        current_text = current.text() if current else None
        self._list.clear()
        for s in self._sources:
            self._list.addItem(s)
        if current_text:
            items = self._list.findItems(current_text, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.MatchFlag.MatchExactly)
            if items:
                self._list.setCurrentItem(items[0])
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/panes/sources_pane.py
git commit -m "feat: sources pane with directory picker"
```

---

## Task 11: Files pane

**Files:**
- Create: `image_mover/ui/panes/files_pane.py`

- [ ] **Step 1: Implement files_pane.py**

```python
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

from image_mover.core.cache import Cache
from image_mover.core.models import MediaFile


class FilesPane(QWidget):
    file_selected = pyqtSignal(object)  # emits MediaFile

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._files: list[MediaFile] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("Files"))

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Date", "Type"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._table)

    def set_db(self, db):
        self._db = db

    def load_source(self, source_dir: str):
        if not self._db:
            return
        cache = Cache(self._db)
        all_files = cache.get_all_files()
        self._files = [f for f in all_files if any(p.startswith(source_dir) for p in f.paths)]
        self._populate()

    def refresh(self):
        if self._files and self._db:
            source = self._files[0].paths[0] if self._files else ""
            import os
            self.load_source(os.path.dirname(source))

    def _populate(self):
        self._table.setRowCount(0)
        for f in self._files:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name = f.paths[0].split("/")[-1]
            date_str = f.canonical_date.strftime("%Y-%m-%d") if f.canonical_date else "—"
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(date_str))
            type_item = QTableWidgetItem(f.media_type)
            if f.is_duplicate:
                for col in range(3):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(QColor(80, 40, 40))
                type_item.setText(f"{f.media_type} [DUP]")
            self._table.setItem(row, 2, type_item)

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self._files):
            self.file_selected.emit(self._files[row])
```

Also add `get_all_files` to `Cache` in `image_mover/core/cache.py`:

```python
def get_all_files(self) -> list[MediaFile]:
    return [self._doc_to_media_file(doc) for doc in self._files.find()]
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/panes/files_pane.py image_mover/core/cache.py
git commit -m "feat: files pane with duplicate highlighting"
```

---

## Task 12: Preview pane

**Files:**
- Create: `image_mover/ui/panes/preview_pane.py`

- [ ] **Step 1: Implement preview_pane.py**

```python
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from image_mover.core.models import MediaFile


class PreviewPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._thumb = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._thumb.setMinimumHeight(200)
        layout.addWidget(self._thumb)

        self._name = QLabel()
        self._name.setWordWrap(True)
        self._size = QLabel()
        self._date = QLabel()
        self._type = QLabel()
        self._dupe = QLabel()
        self._dupe.setStyleSheet("color: #e07070;")

        for lbl in (self._name, self._size, self._date, self._type, self._dupe):
            layout.addWidget(lbl)
        layout.addStretch()

    def show_file(self, f: MediaFile):
        path = Path(f.primary_path)
        self._name.setText(path.name)
        self._size.setText(f"{f.size_bytes / 1024:.1f} KB")
        self._date.setText(f.canonical_date.strftime("%Y-%m-%d %H:%M") if f.canonical_date else "—")
        self._type.setText(f.media_type)
        self._dupe.setText(f"⚠ Duplicate ({len(f.paths)} copies)" if f.is_duplicate else "")

        if f.media_type == "image" and path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._thumb.setPixmap(
                    pix.scaled(300, 250, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
                return
        self._thumb.setText("(no preview)")
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/panes/preview_pane.py
git commit -m "feat: preview pane with thumbnail and metadata"
```

---

## Task 13: Scan dialog

**Files:**
- Create: `image_mover/ui/dialogs/scan_dialog.py`

- [ ] **Step 1: Implement scan_dialog.py**

```python
from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QFileDialog, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal

from image_mover.ui.workers.scan_worker import ScanWorker


class ScanDialog(QDialog):
    scan_complete = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan Directory")
        self.setMinimumWidth(420)
        self._db = db
        self._worker = None

        layout = QVBoxLayout(self)

        self._dir_label = QLabel("No directory selected")
        layout.addWidget(self._dir_label)

        btn_row = QHBoxLayout()
        btn_pick = QPushButton("Choose directory…")
        btn_pick.clicked.connect(self._pick_dir)
        btn_row.addWidget(btn_pick)
        self._btn_start = QPushButton("Start scan")
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._start_scan)
        btn_row.addWidget(self._btn_start)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self.accept)
        layout.addWidget(self._btn_close)

        self._selected_dir: str | None = None

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select directory to scan")
        if path:
            self._selected_dir = path
            self._dir_label.setText(path)
            self._btn_start.setEnabled(True)

    def _start_scan(self):
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._btn_start.setEnabled(False)
        self._worker = ScanWorker(self._selected_dir, self._db, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._status.setText(f"Scanning… {current}/{total}")

    def _on_finished(self, scanned: int, new: int, dupes: int):
        self._status.setText(f"Done: {scanned} files, {new} new, {dupes} duplicate groups")
        self._progress.setVisible(False)
        self._btn_start.setEnabled(True)
        self.scan_complete.emit()

    def _on_error(self, msg: str):
        self._status.setText(f"Error: {msg}")
        self._progress.setVisible(False)
        self._btn_start.setEnabled(True)
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/dialogs/scan_dialog.py
git commit -m "feat: scan dialog with progress"
```

---

## Task 14: Consolidate dialog

**Files:**
- Create: `image_mover/ui/dialogs/consolidate_dialog.py`

- [ ] **Step 1: Implement consolidate_dialog.py**

```python
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal

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

        cache = Cache(db) if db else None
        groups = cache.get_duplicates() if cache else []
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
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_confirm = QPushButton("Remove duplicates")
        self._btn_confirm.setEnabled(bool(files_to_remove))
        self._btn_confirm.clicked.connect(lambda: self._start(files_to_remove))
        btn_row.addWidget(self._btn_confirm)
        layout.addLayout(btn_row)

    def _start(self, files: list[MediaFile]):
        self._btn_confirm.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = MoveWorker(files, destination="", db=self._db, mode="consolidate", parent=self)
        self._worker.progress.connect(lambda n, t: (self._progress.setRange(0, t), self._progress.setValue(n)))
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(lambda msg: self._status.setText(msg))
        self._worker.start()

    def _on_done(self, moved: int, errors: int):
        self._status.setText(f"Removed {moved} files. {errors} errors.")
        self._progress.setVisible(False)
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/dialogs/consolidate_dialog.py
git commit -m "feat: consolidate dialog with dedup summary"
```

---

## Task 15: Migrate dialog

**Files:**
- Create: `image_mover/ui/dialogs/migrate_dialog.py`

- [ ] **Step 1: Implement migrate_dialog.py**

```python
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

        # Images first, then videos
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
```

- [ ] **Step 2: Commit**

```bash
git add image_mover/ui/dialogs/migrate_dialog.py
git commit -m "feat: migrate dialog with YYYY/MM/DD destination"
```

---

## Task 16: Settings dialog + app entry point

**Files:**
- Create: `image_mover/ui/dialogs/settings_dialog.py`
- Create: `image_mover/ui/app.py`

- [ ] **Step 1: Implement settings_dialog.py**

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from image_mover.core.cache import Cache


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._db = db
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Cache"))
        btn = QPushButton("Clear cache (files + scan history)")
        btn.clicked.connect(self._clear_cache)
        layout.addWidget(btn)
        layout.addStretch()

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "Clear cache",
            "This removes all cached file hashes and scan history. Continue?",
        )
        if reply == QMessageBox.StandardButton.Yes and self._db:
            Cache(self._db).clear()
            QMessageBox.information(self, "Done", "Cache cleared.")
```

- [ ] **Step 2: Implement app.py**

```python
import sys
from PyQt6.QtWidgets import QApplication
from image_mover.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Mover")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the app to verify it launches**

```bash
image-mover
```

Expected: Three-pane window opens with toolbar containing Scan, Consolidate, Migrate, Settings. MongoDB warning appears if `labpi01.local` is unreachable.

- [ ] **Step 4: Commit**

```bash
git add image_mover/ui/dialogs/settings_dialog.py image_mover/ui/app.py
git commit -m "feat: settings dialog and app entry point — app launchable"
```

---

## Task 17: Wire sources pane to files pane

**Files:**
- Modify: `image_mover/ui/main_window.py`
- Modify: `image_mover/ui/panes/files_pane.py`

The `FilesPane` needs the db reference and the sources pane must call `files_pane.load_source` when a scan completes on a source directory.

- [ ] **Step 1: Pass db to FilesPane in main_window.py**

In `_build_panes`, after creating `self._files`:

```python
self._files = FilesPane()
self._files.set_db(self._db)
```

The signal connection already set in Task 9 (`self._sources.source_selected.connect(self._files.load_source)`) works unchanged.

- [ ] **Step 2: Update scan_dialog to emit source dir**

Modify `ScanDialog.scan_complete` to carry the scanned directory path:

In `scan_dialog.py`, change:
```python
scan_complete = pyqtSignal()
```
to:
```python
scan_complete = pyqtSignal(str)  # emits source_dir
```

And in `_on_finished`:
```python
self.scan_complete.emit(self._selected_dir)
```

In `main_window.py`, update the connection:
```python
dlg.scan_complete.connect(lambda path: (self._sources.refresh(), self._files.load_source(path)))
```

- [ ] **Step 3: Manual test**

```bash
image-mover
```

1. Click "+" → pick a small directory of images
2. Click "Scan" → pick same directory → scan completes
3. Select the source in Sources pane → Files pane populates
4. Click a file → Preview pane shows thumbnail and metadata

- [ ] **Step 4: Commit**

```bash
git add image_mover/ui/main_window.py image_mover/ui/panes/files_pane.py image_mover/ui/dialogs/scan_dialog.py
git commit -m "feat: wire sources → files pane, scan refreshes file list"
```

---

## Task 18: Run full test suite

- [ ] **Step 1: Run all tests**

```bash
pytest -v
```

Expected: all tests in `tests/core/` and `tests/workers/` pass.

- [ ] **Step 2: Update CLAUDE.md with run commands**

Add to `CLAUDE.md`:

```markdown
## Commands

- Install: `pip install -e ".[dev]"`
- Run app: `image-mover`
- Run tests: `pytest -v`
- Run single test: `pytest tests/core/test_hasher.py -v`
```

- [ ] **Step 3: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with dev commands"
```
