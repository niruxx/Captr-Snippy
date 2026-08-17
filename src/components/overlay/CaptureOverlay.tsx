import { useEffect, useRef, useState } from "react";
import { emit } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getVirtualScreen } from "../../lib/ipc";

interface Point {
  x: number;
  y: number;
}

/**
 * Frameless, translucent, always-on-top window spanning the full virtual
 * desktop - direct port of views/capture_overlay.py. Dimmed background,
 * crosshair cursor, drag-to-select with a live W x H readout, Esc to
 * cancel. Runs in its own Tauri window/JS context, so it hands the
 * selection (or cancellation) back to the main window via a Tauri event
 * rather than shared state.
 */
export function CaptureOverlay() {
  const [start, setStart] = useState<Point | null>(null);
  const [end, setEnd] = useState<Point | null>(null);
  const origin = useRef({ x: 0, y: 0 });

  useEffect(() => {
    getVirtualScreen().then((vs) => {
      if (vs) origin.current = { x: vs.x, y: vs.y };
    });
    getCurrentWindow().setFocus().catch(() => {});

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") cancel();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  async function cancel() {
    await emit("capture:cancelled");
    await getCurrentWindow().close();
  }

  function handleMouseDown(e: React.MouseEvent) {
    const p = { x: e.clientX, y: e.clientY };
    setStart(p);
    setEnd(p);
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!start) return;
    setEnd({ x: e.clientX, y: e.clientY });
  }

  async function handleMouseUp() {
    if (!start || !end) return;
    const dpr = window.devicePixelRatio || 1;
    const toGlobal = (p: Point) => ({
      x: Math.round(origin.current.x + p.x * dpr),
      y: Math.round(origin.current.y + p.y * dpr),
    });
    const g1 = toGlobal(start);
    const g2 = toGlobal(end);
    setStart(null);
    setEnd(null);
    await emit("capture:region-selected", { x1: g1.x, y1: g1.y, x2: g2.x, y2: g2.y });
    await getCurrentWindow().close();
  }

  const rect =
    start && end
      ? {
          left: Math.min(start.x, end.x),
          top: Math.min(start.y, end.y),
          width: Math.abs(end.x - start.x),
          height: Math.abs(end.y - start.y),
        }
      : null;
  const dpr = window.devicePixelRatio || 1;

  return (
    <div
      className="h-screen w-screen cursor-crosshair bg-black/40"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {rect && (
        <div
          className="absolute border-2 border-[#4285f4] bg-[#4285f4]/10 shadow-[0_0_0_1px_rgba(66,133,244,0.4)]"
          style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}
        >
          <span className="absolute -top-7 left-0 rounded-md bg-[#202124]/95 px-2.5 py-1 text-xs font-medium text-white shadow-lg">
            {Math.round(rect.width * dpr)} × {Math.round(rect.height * dpr)}
          </span>
        </div>
      )}
    </div>
  );
}
