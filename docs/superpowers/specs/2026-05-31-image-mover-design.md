# image-mover Design Spec
*2026-05-31*

## Overview

A macOS desktop application to consolidate and organize personal image and video libraries. It deduplicates files by SHA-256 hash, migrates them into a `YYYY/MM/DD` directory structure, and caches all file metadata in MongoDB to avoid redundant hashing across sessions.

---

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| UI framework | PyQt6 |
| Database | MongoDB (`mongodb://labpi01.local:27017/`, db: `image_mover`) |
| Hashing | SHA-256 streaming (64 KB chunks) |
| Metadata | `exifread` library for EXIF extraction |
| Video metadata | `pymediainfo` (Python library, no external binary required) |

---

## Supported File Formats

**Images:** `.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.pef`

**Videos:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.mts`, `.m2ts`, `.3gp`, `.wmv`

---

## Architecture

Layered architecture: a pure Python `core` library handles all business logic; PyQt6 is a thin presentation layer; background work runs in `QThread` workers.

```
image_mover/
  core/
    scanner.py        # walk source dirs, extract metadata
    hasher.py         # streaming SHA-256
    deduplicator.py   # group by hash, select oldest copy
    organizer.py      # move files into dest/YYYY/MM/DD/
    cache.py          # MongoDB read/write
    models.py         # MediaFile, ScanSession, DuplicateGroup dataclasses
  ui/
    app.py            # QApplication entry point
    main_window.py    # three-pane shell + toolbar
    panes/
      sources_pane.py    # left: scanned source directories
      files_pane.py      # center: file list with duplicate flags
      preview_pane.py    # right: thumbnail + metadata
    dialogs/
      scan_dialog.py
      consolidate_dialog.py
      migrate_dialog.py
      settings_dialog.py
    workers/
      scan_worker.py     # QThread: scanner + hasher
      move_worker.py     # QThread: organizer
```

Images and videos use the same pipeline, tagged with `media_type: image | video`. The UI can filter by media type independently.

---

## UI Layout

Three-pane window with toolbar:

```
┌─────────────────────────────────────────────────────┐
│  [Scan]  [Consolidate]  [Migrate]  [Settings]       │  ← toolbar
├──────────────┬──────────────────┬───────────────────┤
│  Sources     │  Files           │  Preview          │
│              │                  │                   │
│  📁 /Photos  │  🖼 IMG_4021.JPG │  [thumbnail]      │
│  📁 /Downloads│ 🖼 IMG_4021_copy │                   │
│              │    [DUP]         │  IMG_4021.JPG     │
│  + Add…      │  🎬 VID_0043.MP4 │  4.2 MB           │
│              │  🖼 IMG_4022.JPG │  2021-06-12       │
│              │                  │  4032 × 3024      │
└──────────────┴──────────────────┴───────────────────┘
│  Status bar: Ready · 8,241 files · 37 duplicates    │
└─────────────────────────────────────────────────────┘
```

---

## Data Model (MongoDB)

### Collection: `files`

`_id` is the SHA-256 hash. Duplicate files share the same document with multiple entries in `paths`.

```json
{
  "_id": "<sha256>",
  "paths": ["/Photos/IMG_4021.JPG", "/Downloads/IMG_4021 copy.JPG"],
  "media_type": "image",
  "size_bytes": 4404224,
  "exif_date": "2021-06-12T14:32:00",
  "file_date": "2021-06-12T14:32:00",
  "canonical_date": "2021-06-12T14:32:00",
  "extension": ".jpg",
  "last_seen": "2026-05-31T10:00:00",
  "migrated_to": null
}
```

`canonical_date` = EXIF date if available, otherwise `file_date`. `file_date` is `st_birthtime` (macOS creation time) when non-zero, falling back to `st_mtime` (modification time).

### Collection: `scan_sessions`

```json
{
  "_id": "<uuid>",
  "source_dir": "/Photos",
  "started_at": "2026-05-31T10:00:00",
  "completed_at": "2026-05-31T10:04:12",
  "files_scanned": 8241,
  "files_new": 142,
  "duplicates_found": 37
}
```

### Collection: `settings`

```json
{
  "_id": "config",
  "supported_extensions": [".jpg", "..."],
  "last_destination": "/Consolidated"
}
```

---

## Key Workflows

### Scan
1. User clicks "+" in Sources pane → directory picker opens
2. `ScanWorker` walks the directory recursively, filtering by extension allowlist
3. Per file: check MongoDB by path + size + mtime — if unchanged since last scan, skip hashing
4. Otherwise: stream SHA-256 → upsert into `files` (append path if hash already exists)
5. Worker emits `progress(n, total)` and `file_found(MediaFile)` signals → UI updates live
6. Sources pane shows file count and duplicate badge on completion

### Consolidation (deduplication)
1. User clicks "Consolidate" → app queries `files` where `len(paths) > 1`
2. Per duplicate group: keeper = path with oldest `canonical_date`
3. `ConsolidateDialog` shows summary: N groups, M files to remove, space to reclaim
4. User confirms → `MoveWorker` deletes non-keeper paths
5. MongoDB `paths` arrays trimmed to keeper only; UI refreshes

### Migration (organize)
1. User clicks "Migrate" → destination directory picker opens
2. `MoveWorker` iterates `files` where `migrated_to` is null
3. Per file: compute `dest/YYYY/MM/DD/filename`; handle collisions with `_1`, `_2` suffix
4. Move file → set `migrated_to` in MongoDB
5. Images processed first, then videos — separate progress bars
6. Post-run report lists any errors (missing source, permission denied)

### Clear Cache
Settings → drops `files` + `scan_sessions` collections (confirmation required). `settings` collection is preserved.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| MongoDB unreachable at startup | Warning banner; app opens in cache-disabled mode (re-hashes every scan) |
| File permission denied during scan | Skip + log; shown in post-scan summary |
| File missing at migration time | Skip + log; path removed from MongoDB |
| Filename collision at destination | Auto-append `_1`, `_2`, … suffix |

---

## Testing Strategy

- `core/` modules tested with `pytest`, temp directories, and a `image_mover_test` MongoDB database
- `hasher.py`: verified against known SHA-256 values
- `deduplicator.py`: synthetic duplicate groups with varying dates
- `organizer.py`: temp dirs, verifies `YYYY/MM/DD` structure and collision handling
- Workers: core modules mocked, signals asserted in order
- No UI automation tests (PyQt6 end-to-end testing is fragile; manual verification used)
