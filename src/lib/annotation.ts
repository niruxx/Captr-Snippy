// Pure Canvas2D drawing functions - a direct port of annotation.py's
// pure-PIL helpers (draw_arrow/draw_highlight/pixelate_region) plus the
// straightforward tools PIL's ImageDraw handled inline in preview_canvas.py.
// Everything here draws directly in image-pixel space (the canvas's own
// pixel buffer, not its CSS-scaled display size), exactly like PIL drew
// directly onto the full-resolution image.

export type ToolName =
  | "pen"
  | "highlight"
  | "line"
  | "arrow"
  | "rect"
  | "ellipse"
  | "text"
  | "redact"
  | "picker"
  | "crop";

export interface Point {
  x: number;
  y: number;
}

export interface Box {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export function sortedBox(p0: Point, p1: Point): Box {
  return {
    x0: Math.min(p0.x, p1.x),
    y0: Math.min(p0.y, p1.y),
    x1: Math.max(p0.x, p1.x),
    y1: Math.max(p0.y, p1.y),
  };
}

export function drawLine(ctx: CanvasRenderingContext2D, p0: Point, p1: Point, width: number, color: string) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(p0.x, p0.y);
  ctx.lineTo(p1.x, p1.y);
  ctx.stroke();
}

export function drawArrow(ctx: CanvasRenderingContext2D, p0: Point, p1: Point, width: number, color: string) {
  drawLine(ctx, p0, p1, width, color);

  const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x);
  const head = Math.max(12, width * 3.5);
  const spread = 0.5;
  const left: Point = {
    x: p1.x - head * Math.cos(angle - spread),
    y: p1.y - head * Math.sin(angle - spread),
  };
  const right: Point = {
    x: p1.x - head * Math.cos(angle + spread),
    y: p1.y - head * Math.sin(angle + spread),
  };
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(p1.x, p1.y);
  ctx.lineTo(left.x, left.y);
  ctx.lineTo(right.x, right.y);
  ctx.closePath();
  ctx.fill();
}

export function drawPenStroke(ctx: CanvasRenderingContext2D, points: Point[], width: number, color: string) {
  if (points.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (const p of points.slice(1)) ctx.lineTo(p.x, p.y);
  ctx.stroke();
}

export function drawRect(ctx: CanvasRenderingContext2D, box: Box, width: number, color: string) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.strokeRect(box.x0, box.y0, box.x1 - box.x0, box.y1 - box.y0);
}

export function drawEllipse(ctx: CanvasRenderingContext2D, box: Box, width: number, color: string) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  const cx = (box.x0 + box.x1) / 2;
  const cy = (box.y0 + box.y1) / 2;
  const rx = Math.max((box.x1 - box.x0) / 2, 0.01);
  const ry = Math.max((box.y1 - box.y0) / 2, 0.01);
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();
}

export function drawHighlight(ctx: CanvasRenderingContext2D, box: Box, color: string) {
  ctx.save();
  ctx.globalAlpha = 80 / 255;
  ctx.fillStyle = color;
  ctx.fillRect(box.x0, box.y0, box.x1 - box.x0, box.y1 - box.y0);
  ctx.restore();
}

export function drawText(ctx: CanvasRenderingContext2D, pos: Point, text: string, size: number, color: string) {
  ctx.fillStyle = color;
  ctx.font = `700 ${size}px "Segoe UI", sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillText(text, pos.x, pos.y);
}

/** Bakes a mosaic over `box` - direct port of annotation.py's
 * pixelate_region (bilinear downscale, nearest-neighbor upscale). */
export function pixelateRegion(ctx: CanvasRenderingContext2D, box: Box) {
  const x0 = Math.max(0, Math.round(box.x0));
  const y0 = Math.max(0, Math.round(box.y0));
  const x1 = Math.min(ctx.canvas.width, Math.round(box.x1));
  const y1 = Math.min(ctx.canvas.height, Math.round(box.y1));
  const w = x1 - x0;
  const h = y1 - y0;
  if (w < 2 || h < 2) return;

  const factor = Math.max(1, Math.floor(Math.min(w, h) / 12));
  const smallW = Math.max(1, Math.floor(w / factor));
  const smallH = Math.max(1, Math.floor(h / factor));

  const small = document.createElement("canvas");
  small.width = smallW;
  small.height = smallH;
  const sctx = small.getContext("2d")!;
  sctx.drawImage(ctx.canvas, x0, y0, w, h, 0, 0, smallW, smallH);

  ctx.save();
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(x0, y0, w, h);
  ctx.drawImage(small, 0, 0, smallW, smallH, x0, y0, w, h);
  ctx.restore();
}

export function pickColorAt(ctx: CanvasRenderingContext2D, pos: Point): string {
  const x = Math.min(Math.max(Math.round(pos.x), 0), ctx.canvas.width - 1);
  const y = Math.min(Math.max(Math.round(pos.y), 0), ctx.canvas.height - 1);
  const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}
