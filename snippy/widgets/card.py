"""Card - replaces GlassCard. A translucent QFrame styled via QSS
(`QFrame#Card` in theme.py) with a soft drop shadow for elevation - the
frosted-glass panel primitive used throughout the app.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout


class Card(QFrame):
    def __init__(self, parent=None, padding=14, spacing=8):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(padding, padding, padding, padding)
        self.layout_.setSpacing(spacing)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 55))
        self.setGraphicsEffect(shadow)

    def addWidget(self, *args, **kwargs):
        self.layout_.addWidget(*args, **kwargs)

    def addLayout(self, *args, **kwargs):
        self.layout_.addLayout(*args, **kwargs)
