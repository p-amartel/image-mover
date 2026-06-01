import sys
from PyQt6.QtWidgets import QApplication
from image_mover.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Mover")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
