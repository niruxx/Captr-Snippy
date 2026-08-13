import { useEffect, useRef, useState } from "react";
import { useCaptureStore } from "../../state/captureStore";
import { Icon } from "../icons/Icon";
import {
  drawArrow,
  drawEllipse,
  drawHighlight,
  drawLine,
  drawPenStroke,
  drawRect,
  drawText,
  pickColorAt,
  pixelateRegion,
  sortedBox,
  type Point,
} from "../../lib/annotation";

const MOVE_THRESHOLD = 3;

/**
 * The annotation surface - two stacked canvases at the image's native
 * resolution: a base canvas holding the bitmap plus every committed
 * annotation (mutated directly on each tool commit, mirroring PIL's
 * in-place drawing), and an overlay canvas cleared/redrawn on every
 * pointer-move for the drag rubber-band. Direct port of
 * views/preview_canvas.py's paintEvent/mouse handlers, minus the QPainter
 * panel chrome (that's plain CSS here).
 */
export function PreviewCanvas() {
  const screenshot = useCaptureStore((s) => s.screenshot);
  const captureSeq = useCaptureStore((s) => s.captureSeq);
  const tool = useCaptureStore((s) => s.tool);
  const color = useCaptureStore((s) => s.color);
  const width = useCaptureStore((s) => s.width);
  const setScreenshot = useCaptureStore((s) => s.setScreenshot);
  const setColor = useCaptureStore((s) => s.setColor);
  const pushUndo = useCaptureStore((s) => s.pushUndo);
  const popUndo = useCaptureStore((s) => s.popUndo);

  const baseRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const dragStart = useRef<Point | null>(null);
  const dragEnd = useRef<Point | null>(null);
  const penPoints = useRef<Point[]>([]);
  const [, forceRedrawTick] = useState(0);

  // Load the current screenshot's bitmap onto the base canvas whenever it
  // changes (new capture, undo, or our own just-committed edit).
  useEffect(() => {
    const canvas = baseRef.current;
    const overlay = overlayRef.current;
    if (!canvas || !overlay || !screenshot) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = new Image();
    img.onload = () => {
      canvas.width = screenshot.width;
      canvas.height = screenshot.height;
      overlay.width = screenshot.width;
      overlay.height = screenshot.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = screenshot.data_url;
  }, [screenshot]);

  function pixelsPerCssPixel(canvas: HTMLCanvasElement) {
    const rect = canvas.getBoundingClientRect();
    return rect.width > 0 ? canvas.width / rect.width : 1;
  }

  function toImagePoint(e: React.MouseEvent): Point | null {
    const canvas = overlayRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scale = pixelsPerCssPixel(canvas);
    const x = (e.clientX - rect.left) * scale;
    const y = (e.clientY - rect.top) * scale;
    return { x: Math.min(Math.max(x, 0), canvas.width), y: Math.min(Math.max(y, 0), canvas.height) };
  }

  function clearOverlay() {
    const overlay = overlayRef.current;
    const ctx = overlay?.getContext("2d");
    if (overlay && ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
  }

  function paintLivePreview() {
    const overlay = overlayRef.current;
    const ctx = overlay?.getContext("2d");
    const start = dragStart.current;
    const end = dragEnd.current;
    if (!overlay || !ctx || !start || !end) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const box = sortedBox(start, end);
    const effWidth = Math.max(1, Math.round(width * pixelsPerCssPixel(overlay)));

    switch (tool) {
      case "pen":
        drawPenStroke(ctx, penPoints.current, effWidth, color);
        break;
      case "line":
        drawLine(ctx, start, end, effWidth, color);
        break;
      case "arrow":
        drawArrow(ctx, start, end, effWidth, color);
        break;
      case "rect":
        drawRect(ctx, box, effWidth, color);
        break;
      case "ellipse":
        drawEllipse(ctx, box, effWidth, color);
        break;
      case "highlight":
        drawHighlight(ctx, box, color);
        break;
      case "redact": {
        ctx.save();
        ctx.globalAlpha = 130 / 255;
        ctx.fillStyle = "#FF453A";
        ctx.fillRect(box.x0, box.y0, box.x1 - box.x0, box.y1 - box.y0);
        ctx.restore();
        break;
      }
      case "crop": {
        ctx.save();
        ctx.strokeStyle = "#8C7CFF";
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = 1.5;
        ctx.strokeRect(box.x0, box.y0, box.x1 - box.x0, box.y1 - box.y0);
        ctx.restore();
        break;
      }
    }
  }

  function commitToBase(draw: (ctx: CanvasRenderingContext2D) => void) {
    const canvas = baseRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !screenshot) return;
    pushUndo();
    draw(ctx);
    const dataUrl = canvas.toDataURL("image/png");
    setScreenshot({ width: canvas.width, height: canvas.height, data_url: dataUrl });
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (!tool || !screenshot) return;
    const p = toImagePoint(e);
    if (!p) return;
    dragStart.current = p;
    dragEnd.current = p;
    if (tool === "pen") penPoints.current = [p];
    forceRedrawTick((t) => t + 1);
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragStart.current) return;
    const p = toImagePoint(e);
    if (!p) return;
    dragEnd.current = p;
    if (tool === "pen") penPoints.current.push(p);
    paintLivePreview();
  }

  function handleMouseUp() {
    const start = dragStart.current;
    const end = dragEnd.current;
    dragStart.current = null;
    dragEnd.current = null;
    clearOverlay();
    if (!start || !end || !screenshot) return;

    const canvas = baseRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const effWidth = Math.max(1, Math.round(width * pixelsPerCssPixel(overlayRef.current!)));

    if (tool === "text") {
      penPoints.current = [];
      const text = window.prompt("Annotation text:");
      if (!text) return;
      const size = Math.max(16, Math.round(14 + 3 * effWidth));
      commitToBase((c) => drawText(c, end, text, size, color));
      return;
    }

    if (tool === "picker") {
      penPoints.current = [];
      const hex = pickColorAt(ctx, end);
      setColor(hex);
      navigator.clipboard?.writeText(hex).catch(() => {});
      return;
    }

    const moved = Math.hypot(end.x - start.x, end.y - start.y) > MOVE_THRESHOLD;
    if (!moved && tool !== "pen") {
      penPoints.current = [];
      return;
    }

    const box = sortedBox(start, end);
    switch (tool) {
      case "pen": {
        const points = penPoints.current;
        penPoints.current = [];
        if (points.length > 1) commitToBase((c) => drawPenStroke(c, points, effWidth, color));
        break;
      }
      case "line":
        commitToBase((c) => drawLine(c, start, end, effWidth, color));
        break;
      case "arrow":
        commitToBase((c) => drawArrow(c, start, end, effWidth, color));
        break;
      case "rect":
        commitToBase((c) => drawRect(c, box, effWidth, color));
        break;
      case "ellipse":
        commitToBase((c) => drawEllipse(c, box, effWidth, color));
        break;
      case "highlight":
        commitToBase((c) => drawHighlight(c, box, color));
        break;
      case "redact":
        commitToBase((c) => pixelateRegion(c, box));
        break;
      case "crop": {
        const w = box.x1 - box.x0;
        const h = box.y1 - box.y0;
        if (w < 5 || h < 5) {
          popUndo();
          return;
        }
        pushUndo();
        const cropped = document.createElement("canvas");
        cropped.width = Math.round(w);
        cropped.height = Math.round(h);
        cropped.getContext("2d")!.drawImage(canvas, box.x0, box.y0, w, h, 0, 0, w, h);
        setScreenshot({
          width: cropped.width,
          height: cropped.height,
          data_url: cropped.toDataURL("image/png"),
        });
        break;
      }
    }
  }

  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-card border border-highlight-edge bg-surface p-3.5 shadow-lg shadow-black/10 backdrop-blur-xl">
      {!screenshot ? (
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="animate-drift rounded-full bg-linear-to-br from-accent/15 to-accent-glow/15 p-5">
            <Icon name="fullscreen" size={28} className="text-accent" />
          </div>
          <div>
            <p className="text-sm font-medium text-text-secondary">No capture yet</p>
            <p className="text-xs text-text-tertiary">Press Snip region or Full screen to start</p>
          </div>
        </div>
      ) : (
        <div key={captureSeq} className="grid max-h-full max-w-full animate-capture-in place-items-center">
          <canvas ref={baseRef} className="col-start-1 row-start-1 max-h-full max-w-full rounded-[6px] shadow-lg shadow-black/30" />
          <canvas
            ref={overlayRef}
            className="col-start-1 row-start-1 h-full w-full"
            style={{ cursor: tool ? "crosshair" : "default" }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          />
        </div>
      )}
    </div>
  );
}
