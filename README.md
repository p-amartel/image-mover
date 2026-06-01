# image-mover

A macOS desktop app for consolidating and organizing personal image and video libraries. Finds duplicates by SHA-256 hash, migrates files into `YYYY/MM/DD` folder structure, and caches all metadata in MongoDB to avoid redundant work across sessions.

## Features

- **Deduplication** — detects exact duplicates by content hash; keeps the oldest copy, removes the rest
- **Migration** — moves files into `destination/YYYY/MM/DD/` using EXIF date (falls back to file creation date)
- **Persistent cache** — MongoDB stores hashes and scan history so re-scans skip unchanged files
- **Three-pane UI** — Sources / Files / Preview; duplicate rows highlighted in red
- **Broad format support** — JPEG, PNG, HEIC, GIF, BMP, TIFF, WebP, RAW (CR2, CR3, NEF, ARW, DNG, ORF, RW2, PEF) and MP4, MOV, AVI, MKV, MTS, and more
- **Images and videos processed independently**

## Requirements

- macOS (uses `st_birthtime` for file creation dates)
- Python 3.11+
- MongoDB — default: `mongodb://labpi01.local:27017/` (configurable in `main_window.py`)

## Installation

```bash
pip install -e .
```

## Usage

```bash
image-mover
```

**Workflow:**

1. Click **+** in the Sources pane to add a directory → click **Scan**
2. Click **Consolidate** to review and remove duplicate files (keeps oldest copy)
3. Click **Migrate** to move files into `YYYY/MM/DD` structure at a destination you choose
4. **Settings → Clear cache** resets the hash database if needed

If MongoDB is unreachable at startup, the app runs without cache (all files are re-hashed on each scan).

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

## Architecture

```
image_mover/
  core/         # pure Python — no UI dependency
    models.py       # MediaFile, DuplicateGroup, ScanSession
    cache.py        # MongoDB wrapper
    hasher.py       # streaming SHA-256
    scanner.py      # directory walker + EXIF extraction
    deduplicator.py # group files by hash
    organizer.py    # move to YYYY/MM/DD
  ui/
    main_window.py
    panes/          # sources_pane, files_pane, preview_pane
    dialogs/        # scan, consolidate, migrate, settings
    workers/        # QThread workers for scan and move operations
```

The core library has no PyQt6 dependency and can be used headlessly. Workers emit Qt signals for progress updates.
