from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
from image_mover.core.models import MediaFile
from image_mover.ui.workers.move_worker import MoveWorker


def make_file(path="/src/a.jpg"):
    return MediaFile("h1", [path], "image", 1024,
                     datetime(2021,1,1), datetime(2021,1,1), ".jpg")


def test_move_worker_emits_progress(qtbot, tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"\xff\xd8" + b"\x00" * 50)
    files = [make_file(str(src))]
    db = MagicMock()
    worker = MoveWorker(files=files, destinations={"image": str(tmp_path / "dest"), "video": str(tmp_path / "dest")}, db=db, mode="migrate")

    with patch("image_mover.ui.workers.move_worker.Organizer") as MockOrg:
        MockOrg.return_value.move.return_value = "/dest/2021/01/01/a.jpg"
        done = []
        worker.progress.connect(lambda n, t: done.append((n, t)))
        worker.run()

    assert done[-1] == (1, 1)
