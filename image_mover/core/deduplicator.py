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
