"""Color palette and QSS stylesheet generation.

Replaces the Tkinter build's hand-rolled "glass" palette + PIL-rendered
chrome with a flatter, modern-minimal look expressed as native QSS, which
Qt renders anti-aliased for free (no PIL supersampling tricks needed).
"""

import sys


def blend(hex1, hex2, t):
    """Linear blend between two hex colors, t in [0, 1]."""
    c1 = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        round(a + (b - a) * t) for a, b in zip(c1, c2))


def hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


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


def get_palette(dark):
    """A flat, minimal palette - fewer shades than the old "glass" build,
    no translucency layering; elevation comes from a hairline border and a
    soft drop shadow instead of blended glass panels."""
    if dark:
        bg = "#121214"
        surface = "#1B1B1F"
        surface_raised = "#232328"
        white = "#FFFFFF"
        return {
            "bg":              bg,
            "surface":         surface,
            "surface_raised":  surface_raised,
            "border":          blend(bg, white, 0.12),
            "border_soft":     blend(bg, white, 0.07),
            "text":            "#F2F2F4",
            "text_secondary":  blend(bg, white, 0.55),
            "text_tertiary":   blend(bg, white, 0.36),
            "accent":          "#3B82F6",
            "accent_hover":    "#5B94F7",
            "accent_text":     "#FFFFFF",
            "error":           "#F04438",
            "hover":           blend(bg, white, 0.06),
            "pressed":         blend(bg, white, 0.10),
        }
    black = "#000000"
    return {
        "bg":              "#F5F5F7",
        "surface":         "#FFFFFF",
        "surface_raised":  "#FFFFFF",
        "border":          "#E2E2E6",
        "border_soft":     "#EBEBEF",
        "text":            "#1C1C1E",
        "text_secondary":  "#6B6B70",
        "text_tertiary":   "#9A9AA0",
        "accent":          "#2563EB",
        "accent_hover":    "#3B74F0",
        "accent_text":     "#FFFFFF",
        "error":           "#DC2626",
        "hover":           blend("#FFFFFF", black, 0.04),
        "pressed":         blend("#FFFFFF", black, 0.07),
    }


FONT_FAMILY = "Segoe UI"


def build_qss(col):
    """One global stylesheet for the whole window, keyed off dynamic
    properties (e.g. ModernButton's `variant`) instead of custom classes,
    so QSS cascades everywhere and re-theming is just setStyleSheet() again
    - never a widget-tree rebuild."""
    return f"""
    QWidget {{
        background: {col['bg']};
        color: {col['text']};
        font-family: "{FONT_FAMILY}";
        font-size: 10pt;
    }}
    QLabel {{
        background: transparent;
    }}
    QToolTip {{
        background: {col['surface_raised']};
        color: {col['text']};
        border: 1px solid {col['border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    QLineEdit {{
        background: {col['surface']};
        color: {col['text']};
        border: 1px solid {col['border']};
        border-radius: 8px;
        padding: 6px 10px;
        selection-background-color: {col['accent']};
    }}
    QLineEdit:focus {{
        border: 1px solid {col['accent']};
    }}
    QScrollArea {{
        border: none;
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
        background: {col['border']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {col['accent']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
        background: #FFFFFF;
        border: 1px solid {col['border']};
    }}
    QCheckBox::indicator {{
        width: 36px;
        height: 20px;
        border-radius: 10px;
        border: 1px solid {col['border']};
        background: {col['border_soft']};
    }}
    QCheckBox::indicator:checked {{
        background: {col['accent']};
        border: 1px solid {col['accent']};
    }}

    /* ModernButton variants (set via setProperty("variant", ...)) */
    QPushButton {{
        border: none;
        border-radius: 10px;
        padding: 6px 14px;
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
        background: {col['surface']};
        border: 1px solid {col['border']};
    }}
    QPushButton[variant="glass"]:hover {{
        background: {col['hover']};
    }}
    QPushButton[variant="glass"]:pressed {{
        background: {col['pressed']};
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
        background: {col['hover']};
        color: {col['accent']};
    }}
    QPushButton:disabled {{
        color: {col['text_tertiary']};
    }}

    /* Card - a QFrame with objectName "Card" */
    QFrame#Card {{
        background: {col['surface']};
        border: 1px solid {col['border']};
        border-radius: 14px;
    }}

    /* CustomTitleBar */
    QWidget#TitleBar {{
        background: {col['bg']};
        border-bottom: 1px solid {col['border_soft']};
    }}
    QPushButton#TitleBarButton {{
        background: transparent;
        border-radius: 6px;
    }}
    QPushButton#TitleBarButton:hover {{
        background: {col['hover']};
    }}
    QPushButton#TitleBarCloseButton {{
        background: transparent;
        border-radius: 6px;
    }}
    QPushButton#TitleBarCloseButton:hover {{
        background: {col['error']};
        color: #FFFFFF;
    }}

    /* Toast */
    QWidget#Toast {{
        background: {col['surface_raised']};
        border: 1px solid {col['border']};
        border-radius: 20px;
    }}
    """
