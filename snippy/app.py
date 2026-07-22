"""Application entrypoint. Qt handles per-monitor high-DPI scaling and its
own DPI-awareness declaration natively, so unlike the old Tkinter build
there's no manual SetProcessDpiAwareness ctypes call needed before
constructing the application object.
"""

import sys

from PySide6.QtWidgets import QApplication

from .anim import animate
from .landing_window import LandingWindow
from .main_window import FADE_MS, MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Snippy")
    # MainWindow is legitimately hidden (not closed) while recording, and
    # the floating RecordControlBar HUD shown during that time is a
    # Qt::Tool window - which doesn't count towards Qt's default "quit when
    # the last window closes" check anyway. Relying on that default would
    # make the app quit out from under an active recording the moment the
    # landing picker's own window finishes closing, so app lifetime is
    # managed explicitly instead (see MainWindow/LandingWindow closeEvent).
    app.setQuitOnLastWindowClosed(False)

    landing = LandingWindow()
    # keeps the MainWindow instance alive past open_main() returning - a
    # bare local would be garbage-collected as soon as the callback exits
    live = {}

    def open_main(action):
        window = live["window"] = MainWindow()
        window.setWindowOpacity(0.0)
        window.show()
        animate(window, b"windowOpacity", 0.0, 1.0, duration=FADE_MS)
        landing.action_taken = True
        landing.close()
        if action == "screenshot":
            window.start_region_capture()
        elif action == "record":
            window.toggle_recording()

    landing.screenshotRequested.connect(lambda: open_main("screenshot"))
    landing.recordRequested.connect(lambda: open_main("record"))

    landing.setWindowOpacity(0.0)
    landing.show()
    animate(landing, b"windowOpacity", 0.0, 1.0, duration=FADE_MS)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
