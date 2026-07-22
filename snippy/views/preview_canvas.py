"""PreviewCanvas - the annotation surface. Replaces the Tkinter build's
preview `tk.Canvas` + `_draw_preview`/`_to_image`/`_inside_image`/
`_on_preview_press/drag/release`.

A single custom QWidget with `paintEvent`, not QGraphicsView/QGraphicsScene:
annotations are baked onto the underlying PIL image immediately on release
and never re-selected/moved afterward, so a scene graph would buy nothing.
The live drag preview is drawn directly with QPainter (real alpha blending
replaces the old Tk `stipple` translucency hack); the final per-tool commit
stays 100% PIL-based, ported unchanged from annotation.py.
"""

import math

from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QInputDialog,
                               QWidget)

from ..annotation import (draw_arrow, draw_highlight, load_annotation_font,
                          pixelate_region, sorted_box)
from ..theme import GLASS, get_palette, qcolor

PANEL_RADIUS = 22

MOVE_THRESHOLD = 3


class PreviewCanvas(QWidget):
    committed = Signal()          # an edit was baked onto the image
    statusMessage = Signal(str)
    toastRequested = Signal(str)
    colorPicked = Signal(str)     # eyedropper picked a new arbitrary color

    def __init__(self, capture_state, parent=None):
        super().__init__(parent)
        self.state = capture_state
        self._col = get_palette(False)
        self._pixmap = None
        self._scale = None
        self._offset = (0, 0)
        self._drag_start = None
        self._drag_end = None
        self._pen_points = []
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

    def set_palette(self, col):
        self._col = col
        self.update()

    # -- image <-> widget coordinate mapping --------------------------------
    def _rebuild_pixmap(self):
        image = self.state.screenshot
        if image is None:
            self._pixmap = None
            self._scale = None
            return
        w, h = self.width(), self.height()
        iw, ih = image.size
        scale = min(max((w - 28), 1) / iw, max((h - 28), 1) / ih, 1.0)
        tw, th = max(1, round(iw * scale)), max(1, round(ih * scale))
        thumb = image.resize((tw, th), Image.Resampling.LANCZOS)
        self._pixmap = QPixmap.fromImage(ImageQt(thumb.convert("RGBA")))
        self._scale = scale
        self._offset = ((w - tw) // 2, (h - th) // 2)

    def refresh(self):
        self._rebuild_pixmap()
        self.update()

    def resizeEvent(self, event):
        self._rebuild_pixmap()
        super().resizeEvent(event)

    def _to_image(self, x, y):
        if self._scale is None or self.state.screenshot is None:
            return None
        ox, oy = self._offset
        iw, ih = self.state.screenshot.size
        ix = (x - ox) / self._scale
        iy = (y - oy) / self._scale
        return (min(max(ix, 0), iw), min(max(iy, 0), ih))

    def _inside_image(self, x, y):
        if self._scale is None or self.state.screenshot is None:
            return False
        ox, oy = self._offset
        iw, ih = self.state.screenshot.size
        return (ox <= x <= ox + iw * self._scale
                and oy <= y <= oy + ih * self._scale)

    def _to_widget(self, ix, iy):
        ox, oy = self._offset
        return (ox + ix * self._scale, oy + iy * self._scale)

    # -- tool selection -------------------------------------------------------
    def set_tool(self, tool):
        self.state.tool = tool
        self.setCursor(Qt.CursorShape.CrossCursor if tool else Qt.CursorShape.ArrowCursor)

    # -- painting --------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self._col
        panel = QPainterPath()
        panel.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                             PANEL_RADIUS, PANEL_RADIUS)
        painter.fillPath(panel, qcolor(col["tint"], GLASS))
        pen = QPen(QColor(col["highlight_edge"]))
        painter.setPen(pen)
        painter.drawPath(panel)

        if self._pixmap is None:
            painter.setPen(QColor(col["text_secondary"]))
            font = QFont()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No capture yet · press Ctrl+N to snip")
            return

        painter.save()
        painter.setClipPath(panel)
        ox, oy = self._offset
        painter.drawPixmap(int(ox), int(oy), self._pixmap)
        painter.restore()

        if self._drag_start and self._drag_end:
            self._paint_live_preview(painter)

    def _paint_live_preview(self, painter):
        col = self._col
        x0, y0 = self._drag_start
        x1, y1 = self._drag_end
        tool = self.state.tool
        color = QColor(self.state.annot_color)
        width = self.state.annot_width

        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        if tool == "pen":
            painter.setPen(pen)
            pts = [QPointF(*self._to_widget(*p)) for p in self._pen_points]
            for a, b in zip(pts, pts[1:]):
                painter.drawLine(a, b)
            return

        if tool in ("line", "arrow"):
            painter.setPen(pen)
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
            if tool == "arrow":
                angle = math.atan2(y1 - y0, x1 - x0)
                head = max(12, width * 3.5)
                spread = 0.5
                left = QPointF(x1 - head * math.cos(angle - spread),
                              y1 - head * math.sin(angle - spread))
                right = QPointF(x1 - head * math.cos(angle + spread),
                                y1 - head * math.sin(angle + spread))
                painter.setBrush(color)
                painter.drawPolygon([QPointF(x1, y1), left, right])
        elif tool == "rect":
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
        elif tool == "ellipse":
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
        elif tool == "highlight":
            fill = QColor(color)
            fill.setAlpha(80)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
        elif tool == "redact":
            fill = QColor(col["error"])
            fill.setAlpha(130)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
        elif tool == "crop":
            dash_pen = QPen(QColor(col["accent"]))
            dash_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())

    # -- mouse interaction -----------------------------------------------------
    def mousePressEvent(self, event):
        if not self.state.tool or self.state.screenshot is None:
            return
        pos = event.position()
        if not self._inside_image(pos.x(), pos.y()):
            self._drag_start = None
            return
        self._drag_start = (pos.x(), pos.y())
        self._drag_end = self._drag_start
        if self.state.tool == "pen":
            self._pen_points = [self._to_image(pos.x(), pos.y())]
        self.update()

    def mouseMoveEvent(self, event):
        if not self._drag_start:
            return
        pos = event.position()
        self._drag_end = (pos.x(), pos.y())
        if self.state.tool == "pen":
            self._pen_points.append(self._to_image(pos.x(), pos.y()))
        self.update()

    def mouseReleaseEvent(self, event):
        if not self._drag_start:
            return
        start = self._drag_start
        end = self._drag_end
        self._drag_start = None
        self._drag_end = None

        p0 = self._to_image(*start)
        p1 = self._to_image(*end)
        self.update()
        if p0 is None or p1 is None:
            return

        scale = self._scale or 1.0
        eff_w = max(1, round(self.state.annot_width / scale))
        moved = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > MOVE_THRESHOLD
        tool = self.state.tool

        if tool == "text":
            self._pen_points = []
            self._annotate_text(p1)
            return
        if tool == "picker":
            self._pen_points = []
            self._pick_color_at(p1)
            return
        if not moved and tool != "pen":
            self._pen_points = []
            return

        self.state.push_undo()
        img = self.state.screenshot
        color = self.state.annot_color

        if tool == "pen":
            if len(self._pen_points) > 1:
                ImageDraw.Draw(img).line(self._pen_points, fill=color,
                                         width=eff_w, joint="curve")
            self._pen_points = []
        elif tool == "line":
            ImageDraw.Draw(img).line([p0, p1], fill=color, width=eff_w)
        elif tool == "arrow":
            draw_arrow(img, p0, p1, eff_w, color)
        elif tool == "rect":
            box = sorted_box(p0, p1)
            ImageDraw.Draw(img).rectangle(box, outline=color, width=eff_w)
        elif tool == "ellipse":
            box = sorted_box(p0, p1)
            ImageDraw.Draw(img).ellipse(box, outline=color, width=eff_w)
        elif tool == "highlight":
            self.state.screenshot = draw_highlight(img, p0, p1, color)
        elif tool == "redact":
            box = sorted_box(p0, p1)
            self.state.screenshot = pixelate_region(img, box)
        elif tool == "crop":
            box = sorted_box(p0, p1)
            if box[2] - box[0] < 5 or box[3] - box[1] < 5:
                self.state.pop_undo()
                return
            self.state.screenshot = img.crop(tuple(round(v) for v in box))
            self.statusMessage.emit(
                f"Cropped to {self.state.screenshot.width} × "
                f"{self.state.screenshot.height} px")

        self.state.commit()
        self.refresh()
        self.committed.emit()

    def _annotate_text(self, pos):
        text, ok = QInputDialog.getText(self, "Add text", "Annotation text:")
        if not ok or not text:
            return
        self.state.push_undo()
        size = max(16, round(14 + 3 * self.state.annot_width / (self._scale or 1.0)))
        font = load_annotation_font(size)
        ImageDraw.Draw(self.state.screenshot).text(
            pos, text, fill=self.state.annot_color, font=font)
        self.state.commit()
        self.refresh()
        self.committed.emit()

    def _pick_color_at(self, pos):
        image = self.state.screenshot
        x = min(max(int(pos[0]), 0), image.width - 1)
        y = min(max(int(pos[1]), 0), image.height - 1)
        rgb = image.convert("RGB").getpixel((x, y))
        hex_color = "#%02X%02X%02X" % rgb
        self.state.annot_color = hex_color
        QGuiApplication.clipboard().setText(hex_color)
        self.colorPicked.emit(hex_color)
        self.statusMessage.emit(f"Picked {hex_color} · copied to clipboard")
        self.toastRequested.emit(f"Color {hex_color} copied to clipboard")
