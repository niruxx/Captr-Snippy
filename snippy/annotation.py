"""Pure-PIL annotation drawing helpers - the actual pixel edits committed
onto a capture. Framework-agnostic: operate only on PIL Images, no UI
toolkit dependency. The Qt preview surface calls these on mouse-release
exactly as the Tkinter build did; only the live drag-preview rendering
(done with QPainter instead of Tk canvas items) is new.
"""

import math
import sys

from PIL import ImageDraw, ImageFont

from .theme import hex_rgb

ANNOTATION_FONT_CANDIDATES = {
    "win32":  ("segoeui.ttf", "arial.ttf"),
    "darwin": ("SFNSText", "Helvetica", "Arial"),
}
ANNOTATION_FONT_FALLBACK = ("DejaVuSans", "LiberationSans-Regular",
                            "NotoSans-Regular", "Ubuntu-R")


def load_annotation_font(size):
    """Best-effort TrueType lookup by name so annotated text isn't drawn
    with PIL's tiny bitmap default; falls back gracefully if none resolve."""
    candidates = ANNOTATION_FONT_CANDIDATES.get(sys.platform,
                                                ANNOTATION_FONT_FALLBACK)
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sorted_box(p0, p1):
    return (min(p0[0], p1[0]), min(p0[1], p1[1]),
            max(p0[0], p1[0]), max(p0[1], p1[1]))


def draw_arrow(img, p0, p1, width, color):
    draw = ImageDraw.Draw(img)
    draw.line([p0, p1], fill=color, width=width)
    angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    head = max(12, width * 3.5)
    spread = 0.5
    left = (p1[0] - head * math.cos(angle - spread),
            p1[1] - head * math.sin(angle - spread))
    right = (p1[0] - head * math.cos(angle + spread),
             p1[1] - head * math.sin(angle + spread))
    draw.polygon([p1, left, right], fill=color)


def draw_highlight(img, p0, p1, color):
    from PIL import Image
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    box = sorted_box(p0, p1)
    ImageDraw.Draw(overlay).rectangle(box, fill=hex_rgb(color) + (80,))
    return Image.alpha_composite(base, overlay).convert("RGB")


def pixelate_region(img, box):
    """Bakes a mosaic over `box` - for redacting sensitive on-screen
    content before sharing a capture. Irreversible once committed (undo
    restores the pre-redact image, same as any other tool)."""
    from PIL import Image as PILImage
    x0, y0, x1, y1 = (round(v) for v in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return img
    region = img.crop((x0, y0, x1, y1))
    factor = max(1, min(region.width, region.height) // 12)
    small = region.resize(
        (max(1, region.width // factor), max(1, region.height // factor)),
        PILImage.Resampling.BILINEAR)
    mosaic = small.resize(region.size, PILImage.Resampling.NEAREST)
    img.paste(mosaic, (x0, y0))
    return img
