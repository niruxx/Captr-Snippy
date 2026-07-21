"""Application entrypoint. Qt handles per-monitor high-DPI scaling and its
own DPI-awareness declaration natively, so unlike the old Tkinter build
there's no manual SetProcessDpiAwareness ctypes call needed before
constructing the application object.
"""

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Snippy")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
