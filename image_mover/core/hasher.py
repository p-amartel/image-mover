import hashlib
from pathlib import Path

CHUNK_SIZE = 64 * 1024  # 64 KB


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()
