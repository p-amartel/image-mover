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
