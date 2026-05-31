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
