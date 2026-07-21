"""Clipboard image support.

Replaces the Tkinter build's three platform-specific implementations (raw
Win32 CF_DIB via ctypes, osascript on macOS, wl-copy/xclip on Linux) with a
single cross-platform QClipboard call.
"""

from PIL.ImageQt import ImageQt
from PySide6.QtGui import QGuiApplication, QImage


def copy_image_to_clipboard(pil_image):
    qimage = QImage(ImageQt(pil_image.convert("RGBA")))
    QGuiApplication.clipboard().setImage(qimage)
