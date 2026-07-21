"""Card - replaces GlassCard. A plain QFrame styled via QSS
(`QFrame#Card` in theme.py), hosting a QVBoxLayout for its content -
no manual rounded-rect image compositing needed, QSS + QPainter's native
antialiasing draws the rounded panel for free.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout


class Card(QFrame):
    def __init__(self, parent=None, padding=18, spacing=8):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(padding, padding, padding, padding)
        self.layout_.setSpacing(spacing)

    def addWidget(self, *args, **kwargs):
        self.layout_.addWidget(*args, **kwargs)

    def addLayout(self, *args, **kwargs):
        self.layout_.addLayout(*args, **kwargs)
