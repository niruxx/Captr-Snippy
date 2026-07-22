"""Anti-aliased rounded-corner window mask.

`QWidget.setMask()` only accepts a hard-edged `QRegion`, so clipping the
whole frameless window to a `QPainterPath.toFillPolygon().toPolygon()`
rasterizes the rounded corners with no antialiasing at all - at a small
radius this shows up as a visibly "staircased"/pixelated edge, most obvious
along the straight titlebar edge right next to the curve.

The fix: build just the four corner quarter-circles once (small, so cheap)
by supersampling at a higher resolution with antialiasing on, downscaling
with a smooth filter, and thresholding the result into a dithered alpha
mask - the standard Qt trick for softening a binary `QRegion` edge. Cache
per-radius since the corner shape never changes, then compose the full
window region each resize by punching the four corner squares out of a
plain rectangle and unioning the cached antialiased corner regions back in
(cheap: just translations of a cached small QRegion, no re-rendering).
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBitmap, QImage, QPainter, QPainterPath, QRegion

SUPERSAMPLE = 8

_corner_cache = {}


def _build_corner_regions(radius):
    size = radius * SUPERSAMPLE
    img = QImage(size * 2, size * 2, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * 2, size * 2), size, size)
    painter.fillPath(path, Qt.GlobalColor.black)
    painter.end()

    top_left = img.copy(0, 0, size, size).scaled(
        radius, radius, Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    variants = {
        "tl": top_left,
        "tr": top_left.mirrored(True, False),
        "bl": top_left.mirrored(False, True),
        "br": top_left.mirrored(True, True),
    }
    return {
        key: QRegion(QBitmap.fromImage(
            im.createAlphaMask(Qt.ImageConversionFlag.ThresholdAlphaDither)))
        for key, im in variants.items()
    }


def _corners(radius):
    if radius not in _corner_cache:
        _corner_cache[radius] = _build_corner_regions(radius)
    return _corner_cache[radius]


def rounded_region(width, height, radius):
    """A QRegion covering a `width` x `height` rect with anti-aliased
    rounded corners of the given radius."""
    radius = max(0, min(radius, width // 2, height // 2))
    if radius <= 0:
        return QRegion(0, 0, width, height)

    corners = _corners(radius)
    region = QRegion(0, 0, width, height)
    region = region.subtracted(QRegion(0, 0, radius, radius))
    region = region.subtracted(QRegion(width - radius, 0, radius, radius))
    region = region.subtracted(QRegion(0, height - radius, radius, radius))
    region = region.subtracted(QRegion(width - radius, height - radius, radius, radius))

    region = region.united(corners["tl"].translated(0, 0))
    region = region.united(corners["tr"].translated(width - radius, 0))
    region = region.united(corners["bl"].translated(0, height - radius))
    region = region.united(corners["br"].translated(width - radius, height - radius))
    return region
