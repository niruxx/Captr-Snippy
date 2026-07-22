"""Color palette and QSS stylesheet generation.

A soft violet/indigo accent on warm neutral backgrounds, with translucent
glass panels (via `#AARRGGBB` colors - Qt's QSS *and* QColor both parse this
format, so the same palette values work for stylesheet rules and for
QPainter-based custom widgets) and soft drop shadows for elevation. A single
accent hue drives every "active" state (buttons, toggles, selection) rather
than mixing separate brand colors, per DTK convention.
"""

import sys

from PySide6.QtGui import QColor


def blend(hex1, hex2, t):
    """Linear blend between two opaque hex colors, t in [0, 1]."""
    c1 = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        round(a + (b - a) * t) for a, b in zip(c1, c2))


def hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def translucent(hex_color, alpha):
    """`hex_color` (opaque "#RRGGBB") + alpha in [0, 1] -> "#AARRGGBB".
    Understood natively by both QSS and QColor(str), so it's the one color
    format used throughout this app for glass panels."""
    a = round(max(0.0, min(1.0, alpha)) * 255)
    return f"#{a:02X}{hex_color[1:].upper()}"


def qcolor(hex_color, alpha=1.0):
    return QColor(translucent(hex_color, alpha))


def system_dark_mode():
    """True when Windows apps are set to dark appearance."""
    if sys.platform == "win32":
        try:
            import winreg
            key_path = (r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Themes\Personalize")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            pass
    return False


# Standard translucency levels for "glass" surfaces, shared across widgets so
# the whole app reads as one consistent material. DTK's own surfaces read as
# flatter/more opaque than iOS "vibrancy" glass, so these sit high (mostly
# solid) rather than heavily see-through.
GLASS = 0.88          # resting panel (cards)
GLASS_STRONG = 0.96   # panels that float over busy content (toast, record
                      # bar, the contextual annotation toolbar) - effectively
                      # opaque so their contents stay legible over a photo.
BORDER_GLASS = 0.5
HOVER_ALPHA = 0.07
PRESSED_ALPHA = 0.13


def get_palette(dark):
    if dark:
        tint = "#242130"        # panel glass tint - warm, slightly violet charcoal
        white = "#FFFFFF"
        return {
            "bg_top":          "#181622",
            "bg_bottom":       "#100E18",
            "tint":            tint,
            "border":          blend("#000000", white, 0.16),
            "border_soft":     blend("#000000", white, 0.09),
            "text":            "#F3F1FA",
            "text_secondary":  blend("#000000", white, 0.62),
            "text_tertiary":   blend("#000000", white, 0.40),
            "accent":          "#8C7CFF",
            "accent_hover":    "#A398FF",
            "accent_text":     "#FFFFFF",
            "toggle_on":       "#8C7CFF",
            "error":           "#FF6B81",
            "hover":           translucent(white, HOVER_ALPHA),
            "pressed":         translucent(white, PRESSED_ALPHA),
            "shadow":          "#00000090",
            "highlight_edge":  translucent(white, 0.16),
        }
    return {
        "bg_top":          "#F6F5FC",
        "bg_bottom":       "#EEEBF7",
        "tint":            "#FFFFFF",
        "border":          "#E2DFEE",
        "border_soft":     "#EDEBF6",
        "text":            "#1E1B2E",
        "text_secondary":  "#6C6880",
        "text_tertiary":   "#A6A2B8",
        "accent":          "#6C5CE7",
        "accent_hover":    "#8072ED",
        "accent_text":     "#FFFFFF",
        "toggle_on":       "#6C5CE7",
        "error":           "#F0506E",
        "hover":           translucent("#000000", HOVER_ALPHA),
        "pressed":         translucent("#000000", PRESSED_ALPHA),
        "shadow":          "#00000040",
        "highlight_edge":  translucent("#FFFFFF", 0.8),
    }


FONT_FAMILY = "Segoe UI"


def glass(col, alpha=GLASS):
    return translucent(col["tint"], alpha)


def build_qss(col):
    """One global stylesheet for the whole window, keyed off dynamic
    properties (e.g. ModernButton's `variant`) instead of custom classes,
    so QSS cascades everywhere and re-theming is just setStyleSheet() again
    - never a widget-tree rebuild."""
    surface = glass(col, GLASS)
    surface_strong = glass(col, GLASS_STRONG)
    return f"""
    QWidget {{
        background: transparent;
        color: {col['text']};
        font-family: "{FONT_FAMILY}";
        font-size: 9pt;
    }}
    QLabel {{
        background: transparent;
    }}
    QToolTip {{
        background: {surface_strong};
        color: {col['text']};
        border: 1px solid {col['border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QLineEdit {{
        background: {surface};
        color: {col['text']};
        border: 1px solid {col['border']};
        border-radius: 7px;
        padding: 5px 8px;
        selection-background-color: {col['accent']};
    }}
    QLineEdit:focus {{
        border: 1px solid {col['accent']};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {col['border']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {col['text_tertiary']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: {col['border_soft']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {col['accent']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 15px;
        height: 15px;
        margin: -6px 0;
        border-radius: 7px;
        background: #FFFFFF;
        border: 1px solid {col['border']};
    }}
    QCheckBox::indicator {{
        width: 36px;
        height: 22px;
        border-radius: 11px;
        border: 1px solid {col['border']};
        background: {col['border_soft']};
    }}
    QCheckBox::indicator:checked {{
        background: {col['toggle_on']};
        border: 1px solid {col['toggle_on']};
    }}

    /* ModernButton variants (set via setProperty("variant", ...)); the
    per-instance pill radius is set on the widget itself (see buttons.py) */
    QPushButton {{
        border: none;
        padding: 5px 14px;
        background: transparent;
        color: {col['text']};
    }}
    QPushButton[variant="primary"] {{
        background: {col['accent']};
        color: {col['accent_text']};
        font-weight: 600;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {col['accent_hover']};
    }}
    QPushButton[variant="primary"]:pressed {{
        background: {col['accent']};
    }}
    QPushButton[variant="glass"] {{
        background: {surface};
        border: 1px solid {col['border']};
    }}
    QPushButton[variant="glass"]:hover {{
        background: {surface_strong};
    }}
    QPushButton[variant="glass"]:pressed {{
        background: {surface};
    }}
    QPushButton[variant="plain"] {{
        background: transparent;
    }}
    QPushButton[variant="plain"]:hover {{
        background: {col['hover']};
    }}
    QPushButton[variant="plain"]:pressed {{
        background: {col['pressed']};
    }}
    QPushButton[variant="plain"][selected="true"] {{
        background: {translucent(col['accent'], 0.16)};
        color: {col['accent']};
    }}
    QPushButton:disabled {{
        color: {col['text_tertiary']};
    }}

    /* Card - a QFrame with objectName "Card" */
    QFrame#Card {{
        background: {surface};
        border: 1px solid {col['highlight_edge']};
        border-radius: 10px;
    }}

    /* CustomTitleBar - transparent, just a hairline to separate it */
    QWidget#TitleBar {{
        background: transparent;
        border-bottom: 1px solid {col['border_soft']};
    }}
    QLabel#TitleBarLabel {{
        color: {col['text_secondary']};
        font-weight: 600;
    }}
    QPushButton#TitleBarButton {{
        background: transparent;
        border-radius: 8px;
        color: {col['text_secondary']};
    }}
    QPushButton#TitleBarButton:hover {{
        background: {col['hover']};
    }}
    QPushButton#TitleBarCloseButton {{
        background: transparent;
        border-radius: 8px;
        color: {col['text_secondary']};
    }}
    QPushButton#TitleBarCloseButton:hover {{
        background: {col['error']};
        color: #FFFFFF;
    }}

    /* Toast / floating pills painted by their own paintEvent - QSS here
    only styles their child QLabels/QPushButtons */
    QWidget#Toast QLabel {{
        color: {col['text']};
        font-weight: 600;
        background: transparent;
    }}

    /* Overflow ("...") menu */
    QMenu {{
        background: {surface_strong};
        border: 1px solid {col['highlight_edge']};
        border-radius: 8px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 12px;
        border-radius: 6px;
        color: {col['text']};
    }}
    QMenu::item:selected {{
        background: {col['hover']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {col['border_soft']};
        margin: 6px 8px;
    }}
    """
