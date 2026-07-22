"""Hand-drawn vector icons, rendered with QPainter onto a transparent
QPixmap and wrapped as a QIcon.

Replaces every Unicode glyph icon in the app (tool icons, titlebar
controls, record bar, header buttons): those relied on whichever symbol/
emoji font happened to cover a given codepoint, which is inconsistent
across systems and actively wrong on Windows for a few of them (e.g.
"⏸"/"⏹"/"⏺" get rendered as small colored emoji instead of flat
monochrome symbols, since Windows' emoji font claims those codepoints).
Drawing our own icons guarantees a crisp, consistent, themeable result.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

CANVAS = 64


def _pt(x, y, s):
    return QPointF(x * s, y * s)


def _pen(color, s, width_frac=0.09):
    p = QPen(QColor(color))
    p.setWidthF(width_frac * s)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def _draw_pen(p, s, color):
    p.setPen(_pen(color, s))
    p.drawLine(_pt(0.22, 0.82, s), _pt(0.60, 0.32, s))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    nib = QPainterPath()
    nib.moveTo(_pt(0.58, 0.34, s))
    nib.lineTo(_pt(0.74, 0.16, s))
    nib.lineTo(_pt(0.84, 0.26, s))
    nib.lineTo(_pt(0.68, 0.42, s))
    nib.closeSubpath()
    p.drawPath(nib)


def _draw_highlight(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(_pt(0.18, 0.80, s))
    path.lineTo(_pt(0.54, 0.20, s))
    path.lineTo(_pt(0.74, 0.32, s))
    path.lineTo(_pt(0.38, 0.90, s))
    path.closeSubpath()
    p.drawPath(path)


def _draw_line(p, s, color):
    p.setPen(_pen(color, s))
    p.drawLine(_pt(0.18, 0.82, s), _pt(0.82, 0.18, s))


def _draw_arrow(p, s, color):
    p.setPen(_pen(color, s))
    p.drawLine(_pt(0.18, 0.82, s), _pt(0.78, 0.22, s))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    head = QPainterPath()
    head.moveTo(_pt(0.78, 0.22, s))
    head.lineTo(_pt(0.78, 0.46, s))
    head.lineTo(_pt(0.54, 0.22, s))
    head.closeSubpath()
    p.drawPath(head)


def _draw_rect(p, s, color):
    p.setPen(_pen(color, s))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.16 * s, 0.24 * s, 0.68 * s, 0.52 * s), 0.08 * s, 0.08 * s)


def _draw_ellipse(p, s, color):
    p.setPen(_pen(color, s))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(0.14 * s, 0.20 * s, 0.72 * s, 0.60 * s))


def _draw_redact(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(0.14 * s, 0.26 * s, 0.72 * s, 0.48 * s), 0.06 * s, 0.06 * s)


def _draw_picker(p, s, color):
    p.setPen(_pen(color, s, 0.11))
    p.drawLine(_pt(0.28, 0.84, s), _pt(0.58, 0.54, s))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(_pt(0.68, 0.34, s), 0.16 * s, 0.16 * s)


def _draw_crop(p, s, color):
    p.setPen(_pen(color, s, 0.10))
    p.drawLine(_pt(0.22, 0.14, s), _pt(0.22, 0.44, s))
    p.drawLine(_pt(0.22, 0.14, s), _pt(0.52, 0.14, s))
    p.drawLine(_pt(0.78, 0.86, s), _pt(0.78, 0.56, s))
    p.drawLine(_pt(0.78, 0.86, s), _pt(0.48, 0.86, s))


def _draw_undo(p, s, color):
    p.setPen(_pen(color, s, 0.10))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(_pt(0.32, 0.36, s))
    path.cubicTo(_pt(0.86, 0.18, s), _pt(0.88, 0.78, s), _pt(0.44, 0.80, s))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    head = QPainterPath()
    head.moveTo(_pt(0.32, 0.36, s))
    head.lineTo(_pt(0.48, 0.28, s))
    head.lineTo(_pt(0.42, 0.48, s))
    head.closeSubpath()
    p.drawPath(head)


def _draw_text(p, s, color):
    font = QFont("Segoe UI", int(0.42 * s))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "T")


def _draw_settings(p, s, color):
    cx, cy = 0.5 * s, 0.5 * s
    outer_r = 0.24 * s
    tooth_w = 0.12 * s
    tooth_len = 0.13 * s
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    for i in range(8):
        p.save()
        p.translate(cx, cy)
        p.rotate(i * 45)
        p.drawRoundedRect(QRectF(-tooth_w / 2, -(outer_r + tooth_len), tooth_w, tooth_len),
                          tooth_w * 0.3, tooth_w * 0.3)
        p.restore()
    p.drawEllipse(QPointF(cx, cy), outer_r, outer_r)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.drawEllipse(QPointF(cx, cy), outer_r * 0.46, outer_r * 0.46)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


def _draw_more(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    r = 0.065 * s
    for cx in (0.28, 0.5, 0.72):
        p.drawEllipse(QPointF(cx * s, 0.5 * s), r, r)


def _draw_minimize(p, s, color):
    p.setPen(_pen(color, s, 0.10))
    p.drawLine(_pt(0.24, 0.5, s), _pt(0.76, 0.5, s))


def _draw_maximize(p, s, color):
    p.setPen(_pen(color, s, 0.09))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.26 * s, 0.26 * s, 0.48 * s, 0.48 * s), 0.05 * s, 0.05 * s)


def _draw_close(p, s, color):
    p.setPen(_pen(color, s, 0.10))
    p.drawLine(_pt(0.27, 0.27, s), _pt(0.73, 0.73, s))
    p.drawLine(_pt(0.73, 0.27, s), _pt(0.27, 0.73, s))


def _draw_back(p, s, color):
    p.setPen(_pen(color, s, 0.11))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(_pt(0.66, 0.22, s))
    path.lineTo(_pt(0.34, 0.5, s))
    path.lineTo(_pt(0.66, 0.78, s))
    p.drawPath(path)


def _draw_plus(p, s, color):
    p.setPen(_pen(color, s, 0.13))
    p.drawLine(_pt(0.5, 0.24, s), _pt(0.5, 0.76, s))
    p.drawLine(_pt(0.24, 0.5, s), _pt(0.76, 0.5, s))


def _draw_fullscreen(p, s, color):
    p.setPen(_pen(color, s, 0.10))
    arm = 0.16 * s
    corners = ((0.24, 0.24, 1, 1), (0.76, 0.24, -1, 1),
              (0.24, 0.76, 1, -1), (0.76, 0.76, -1, -1))
    for x, y, dx, dy in corners:
        cx, cy = x * s, y * s
        p.drawLine(QPointF(cx, cy), QPointF(cx + dx * arm, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * arm))


def _draw_record(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(0.28 * s, 0.28 * s, 0.44 * s, 0.44 * s))


def _draw_pause(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    bar_w = 0.14 * s
    p.drawRoundedRect(QRectF(0.26 * s, 0.22 * s, bar_w, 0.56 * s), 0.03 * s, 0.03 * s)
    p.drawRoundedRect(QRectF(0.60 * s, 0.22 * s, bar_w, 0.56 * s), 0.03 * s, 0.03 * s)


def _draw_stop(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(0.28 * s, 0.28 * s, 0.44 * s, 0.44 * s), 0.08 * s, 0.08 * s)


def _draw_play(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(_pt(0.32, 0.22, s))
    path.lineTo(_pt(0.32, 0.78, s))
    path.lineTo(_pt(0.80, 0.5, s))
    path.closeSubpath()
    p.drawPath(path)


def _draw_copy(p, s, color):
    pen = _pen(color, s, 0.08)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.20 * s, 0.20 * s, 0.48 * s, 0.48 * s), 0.06 * s, 0.06 * s)
    p.drawRoundedRect(QRectF(0.34 * s, 0.34 * s, 0.48 * s, 0.48 * s), 0.06 * s, 0.06 * s)


_DRAWERS = {
    "pen": _draw_pen,
    "highlight": _draw_highlight,
    "line": _draw_line,
    "arrow": _draw_arrow,
    "rect": _draw_rect,
    "ellipse": _draw_ellipse,
    "text": _draw_text,
    "redact": _draw_redact,
    "picker": _draw_picker,
    "crop": _draw_crop,
    "undo": _draw_undo,
    "settings": _draw_settings,
    "more": _draw_more,
    "minimize": _draw_minimize,
    "maximize": _draw_maximize,
    "close": _draw_close,
    "back": _draw_back,
    "plus": _draw_plus,
    "fullscreen": _draw_fullscreen,
    "record": _draw_record,
    "pause": _draw_pause,
    "play": _draw_play,
    "stop": _draw_stop,
    "copy": _draw_copy,
}


def make_pixmap(name, color, size=CANVAS):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    drawer = _DRAWERS.get(name)
    if drawer:
        drawer(painter, size, color)
    painter.end()
    return pm


def make_icon(name, color, size=CANVAS):
    return QIcon(make_pixmap(name, color, size))
