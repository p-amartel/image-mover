from __future__ import annotations
import pymongo
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar,
    QStatusBar, QLabel, QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from image_mover.core.cache import Cache
from image_mover.ui.panes.sources_pane import SourcesPane
from image_mover.ui.panes.files_pane import FilesPane
from image_mover.ui.panes.preview_pane import PreviewPane

MONGO_URI = "mongodb://labpi01.local:27017/"
DB_NAME = "image_mover"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Mover")
        self.resize(1200, 750)

        self._db = self._connect_mongo()
        self._cache = Cache(self._db) if self._db else None

        self._build_toolbar()
        self._build_panes()
        self._build_status_bar()

    def _connect_mongo(self):
        try:
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            client.server_info()
            return client[DB_NAME]
        except Exception:
            QMessageBox.warning(
                self, "MongoDB unavailable",
                "Cannot reach MongoDB. Running without cache — all files will be re-hashed on each scan."
            )
            return None

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_scan = QAction("Scan", self)
        self._act_consolidate = QAction("Consolidate", self)
        self._act_migrate = QAction("Migrate", self)
        self._act_settings = QAction("Settings", self)

        for act in (self._act_scan, self._act_consolidate, self._act_migrate, self._act_settings):
            tb.addAction(act)

        self._act_scan.triggered.connect(self._on_scan)
        self._act_consolidate.triggered.connect(self._on_consolidate)
        self._act_migrate.triggered.connect(self._on_migrate)
        self._act_settings.triggered.connect(self._on_settings)

    def _build_panes(self):
        self._sources = SourcesPane(self._db)
        self._files = FilesPane()
        self._files.set_db(self._db)
        self._preview = PreviewPane()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sources)
        splitter.addWidget(self._files)
        splitter.addWidget(self._preview)
        splitter.setSizes([220, 400, 380])
        self.setCentralWidget(splitter)

        self._sources.source_selected.connect(self._files.load_source)
        self._files.file_selected.connect(self._preview.show_file)

    def _build_status_bar(self):
        self._status_label = QLabel("Ready")
        sb = QStatusBar()
        sb.addWidget(self._status_label)
        self.setStatusBar(sb)

    def set_status(self, text: str):
        self._status_label.setText(text)

    def _on_scan(self):
        from image_mover.ui.dialogs.scan_dialog import ScanDialog
        dlg = ScanDialog(self._db, self)
        dlg.scan_complete.connect(lambda path: (self._sources.refresh(), self._files.load_source(path)))
        dlg.exec()

    def _on_consolidate(self):
        from image_mover.ui.dialogs.consolidate_dialog import ConsolidateDialog
        dlg = ConsolidateDialog(self._db, self)
        dlg.exec()
        self._files.refresh()

    def _on_migrate(self):
        from image_mover.ui.dialogs.migrate_dialog import MigrateDialog
        dlg = MigrateDialog(self._db, self)
        dlg.exec()
        self._files.refresh()

    def _on_settings(self):
        from image_mover.ui.dialogs.settings_dialog import SettingsDialog
        SettingsDialog(self._db, self).exec()
