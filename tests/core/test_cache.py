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
    assert cache.is_cached("/a.jpg", size_bytes=1024) is True
    assert cache.is_cached("/a.jpg", size_bytes=9999) is False
