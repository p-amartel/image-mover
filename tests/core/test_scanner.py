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
