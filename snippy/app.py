"""Application entrypoint. Qt handles per-monitor high-DPI scaling and its
own DPI-awareness declaration natively, so unlike the old Tkinter build
there's no manual SetProcessDpiAwareness ctypes call needed before
constructing the application object.
"""

import sys

from PySide6.QtWidgets import QApplication

from .anim import animate
from .main_window import FADE_MS, MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Snippy")

    window = MainWindow()
    window.setWindowOpacity(0.0)
    window.show()
    animate(window, b"windowOpacity", 0.0, 1.0, duration=FADE_MS)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
