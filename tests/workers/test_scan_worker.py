from unittest.mock import MagicMock, patch
from datetime import datetime
from image_mover.core.models import MediaFile
from image_mover.ui.workers.scan_worker import ScanWorker


def make_media_file():
    return MediaFile("h1", ["/a.jpg"], "image", 1024,
                     datetime(2021,1,1), datetime(2021,1,1), ".jpg")


def test_scan_worker_emits_progress(qtbot):
    from pathlib import Path
    worker = ScanWorker(source_dir="/tmp", db=MagicMock())
    mock_paths = [(Path("/a.jpg"), ".jpg"), (Path("/b.jpg"), ".jpg")]
    mock_file = make_media_file()

    with patch("image_mover.ui.workers.scan_worker.Scanner") as MockScanner:
        MockScanner.return_value.list_paths.return_value = mock_paths
        MockScanner.return_value.build_media_file.return_value = mock_file
        with patch("image_mover.ui.workers.scan_worker.Cache"):
            signals = []
            worker.progress.connect(lambda n, t: signals.append((n, t)))
            worker.run()

    assert len(signals) == 2
    assert signals[-1] == (2, 2)
