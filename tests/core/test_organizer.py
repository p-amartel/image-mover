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
    # create a second source file with same name
    src2 = tmp_dir / "src2" / "img.jpg"
    src2.parent.mkdir(parents=True, exist_ok=True)
    src2.write_bytes(b"\xff\xd8\xff\xe0" + b"\x01" * 50)
    f2 = MediaFile(
        hash="def",
        paths=[str(src2)],
        media_type="image",
        size_bytes=src2.stat().st_size,
        exif_date=datetime(2021, 6, 12),
        file_date=datetime(2021, 6, 12),
        extension=".jpg",
    )
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
