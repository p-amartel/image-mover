from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from image_mover.core.cache import Cache


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._db = db
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Cache"))
        btn = QPushButton("Clear cache (files + scan history)")
        btn.clicked.connect(self._clear_cache)
        layout.addWidget(btn)
        layout.addStretch()

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "Clear cache",
            "This removes all cached file hashes and scan history. Continue?",
        )
        if reply == QMessageBox.StandardButton.Yes and self._db:
            Cache(self._db).clear()
            QMessageBox.information(self, "Done", "Cache cleared.")
