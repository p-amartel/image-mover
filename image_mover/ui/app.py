import os
import sys
from pathlib import Path


def _ensure_qt_plugins():
    if os.environ.get("QT_PLUGIN_PATH"):
        return
    try:
        import PyQt6
        plugin_path = Path(PyQt6.__file__).parent / "Qt6" / "plugins"
        if plugin_path.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
    except Exception:
        pass


_ensure_qt_plugins()

from PyQt6.QtWidgets import QApplication  # noqa: E402
from image_mover.ui.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Mover")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
