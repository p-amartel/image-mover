# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Install: `pip install -e ".[dev]"`
- Run app: `image-mover`
- Run tests: `pytest -v`
- Run single test: `pytest tests/core/test_hasher.py -v`

## Architecture

Layered: `image_mover/core/` is pure Python business logic; `image_mover/ui/` is a thin PyQt6 presentation layer. Background operations run in `QThread` workers that emit Qt signals.

### Core modules (`image_mover/core/`)

- `models.py` — `MediaFile`, `DuplicateGroup`, `ScanSession` dataclasses. `MediaFile._id` is the SHA-256 hash; duplicates share one doc with multiple `paths`. `canonical_date` prefers EXIF date over file date.
- `cache.py` — `Cache` wraps MongoDB (`mongodb://labpi01.local:27017/`, db `image_mover`). `get_duplicates()` returns `list[DuplicateGroup]` with per-path file dates. `get_all_files()` returns all known files. `clear()` drops `files` + `scan_sessions` collections.
- `hasher.py` — `hash_file(path)` streaming SHA-256 (64 KB chunks).
- `scanner.py` — `Scanner.iter_files(dir)` generator. `IMAGE_EXTS` / `VIDEO_EXTS` sets exported for reuse. EXIF extracted via `exifread`; falls back to `st_birthtime` then `st_mtime`.
- `deduplicator.py` — `build_duplicate_groups(files)` buckets by hash.
- `organizer.py` — `Organizer.move(f)` moves to `dest/YYYY/MM/DD/`, handles collisions with `_1`, `_2` suffix.

### UI (`image_mover/ui/`)

- `main_window.py` — `MainWindow`: connects to MongoDB on startup (warns + continues if unreachable), builds three-pane splitter, wires signals.
- `panes/sources_pane.py` — left pane: source directory list with add button.
- `panes/files_pane.py` — center pane: file table with DUP badge and red row highlight.
- `panes/preview_pane.py` — right pane: QPixmap thumbnail + metadata.
- `workers/scan_worker.py` — `ScanWorker(QThread)`: runs Scanner + hashes, upserts to cache, emits `progress`, `file_found`, `finished`, `error`.
- `workers/move_worker.py` — `MoveWorker(QThread)`: handles `migrate` (Organizer.move + mark_migrated) and `consolidate` (os.remove + remove_path) modes.
- `dialogs/scan_dialog.py` — directory picker + ScanWorker progress. `scan_complete(str)` emits scanned dir.
- `dialogs/consolidate_dialog.py` — shows N groups / M files / MB to reclaim; runs MoveWorker consolidate.
- `dialogs/migrate_dialog.py` — destination picker; runs images then videos through MoveWorker migrate.
- `dialogs/settings_dialog.py` — clear cache with confirmation.

### MongoDB schema

`files` collection: `_id` = SHA-256 hash, `paths` = list of all paths, `path_dates` = dict mapping path→file_date ISO string, `media_type`, `size_bytes`, `exif_date`, `file_date`, `canonical_date`, `extension`, `migrated_to`.

### Testing

Tests use `mongomock` (no real MongoDB needed). `conftest.py` sets `QT_QPA_PLATFORM=offscreen` for headless Qt. Run with plain `pytest -v`.
