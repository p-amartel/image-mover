import hashlib
from pathlib import Path
from image_mover.core.hasher import hash_file


def test_hash_known_content(tmp_dir):
    f = tmp_dir / "test.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert hash_file(f) == expected


def test_hash_large_file_streaming(tmp_dir):
    f = tmp_dir / "big.bin"
    data = b"x" * (200 * 1024)  # 200 KB, crosses chunk boundary
    f.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert hash_file(f) == expected


def test_hash_missing_file_raises(tmp_dir):
    import pytest
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_dir / "nonexistent.jpg")
