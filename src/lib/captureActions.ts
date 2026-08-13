// Orchestrates the region/full-screen capture flows from the main window:
// hide the main window (so it can't appear in its own screenshot), run the
// overlay/delay/grab, then show the main window again with the result.
// Direct behavioral port of main_window.py's start_region_capture()/
// start_fullscreen_capture()/_capture_selection()/_finish_region_capture().
import { listen } from "@tauri-apps/api/event";
import { PhysicalPosition, PhysicalSize } from "@tauri-apps/api/dpi";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { captureFullscreen, captureRegion, getVirtualScreen } from "./ipc";
import { writeCurrentToClipboard } from "./exportActions";
import { playCaptureSound } from "./sound";
import { useCaptureStore } from "../state/captureStore";
import { useSettingsStore } from "../state/settingsStore";
import { useToastStore } from "../state/toastStore";
import type { CapturedImage } from "./types";

const MIN_SELECTION = 5;

/** Adds the capture to history, then - matching main_window.py's
 * `_add_capture()` - auto-copies it to the clipboard when that setting is
 * on, failing silently (a clipboard hiccup shouldn't interrupt capturing). */
async function handleNewCapture(image: CapturedImage) {
  const settings = useSettingsStore.getState().settings;
  useCaptureStore.getState().addCapture(image, settings?.history_limit);
  if (settings?.capture_sound) {
    playCaptureSound();
  }
  if (settings?.auto_copy) {
    try {
      await writeCurrentToClipboard();
      useToastStore.getState().show("Captured · copied to clipboard");
    } catch {
      // matches Python's `except Exception: pass`
    }
  }
}

// `win.hide()` resolving doesn't guarantee the compositor has actually
// stopped presenting the window yet - capturing immediately after risked
// photographing the main window itself mid-hide. The Python/Qt build hit
// this exact race and worked around it the same way (see
// `main_window.py`'s `QTimer.singleShot(200/300 + delay, ...)`).
const HIDE_SETTLE_MS = 250;

function delay(ms: number) {
  return ms > 0 ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve();
}

export async function startFullscreenCapture(delayMs: number) {
  await delay(delayMs);
  const win = getCurrentWindow();
  await win.hide();
  await delay(HIDE_SETTLE_MS);
  try {
    const image = await captureFullscreen();
    await handleNewCapture(image);
  } finally {
    await win.show();
  }
}

export async function startRegionCapture(delayMs: number) {
  await delay(delayMs);
  const win = getCurrentWindow();
  await win.hide();
  await delay(HIDE_SETTLE_MS);

  const vs = await getVirtualScreen();
  const overlay = new WebviewWindow("capture-overlay", {
    decorations: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    shadow: false,
    focus: true,
  });

  // Attach the overlay's own listeners synchronously, in the same tick as
  // construction - `listen()`/`once()` each need their own IPC round-trip
  // to register, and window *creation* (spinning up a real native window +
  // webview) reliably takes longer than that, but only if nothing else is
  // awaited first. The previous version awaited two *other* listen() calls
  // before this one, which was enough extra delay for "tauri://created" to
  // fire and be missed entirely on a warm dev server - silently leaving
  // the overlay stuck at Tauri's 800x600 default size instead of covering
  // the virtual desktop (it never even reached the resize call).
  let settled = false;
  const finish = async () => {
    if (settled) return;
    settled = true;
    unlistenSelected();
    unlistenCancelled();
    await win.show();
  };

  overlay.once("tauri://created", async () => {
    if (!vs) return;
    try {
      // Size before position: on some window managers a resize after the
      // window has already settled at its (default) position can get
      // clamped/ignored if the new size would extend past the work area
      // from the *old* position - sizing first, then moving to the real
      // virtual-desktop origin, avoids that ordering hazard.
      await overlay.setSize(new PhysicalSize(vs.width, vs.height));
      await overlay.setPosition(new PhysicalPosition(vs.x, vs.y));
    } catch (err) {
      useToastStore.getState().show(`Region overlay sizing failed: ${err}`);
      console.error("capture-overlay setSize/setPosition failed:", err);
    }
  });
  overlay.once("tauri://error", async () => {
    await finish();
  });
  overlay.once("tauri://destroyed", async () => {
    // covers the window being closed any other way (e.g. Alt+F4) without
    // either event firing first, so the main window never stays hidden
    await finish();
  });

  const unlistenSelected = await listen<{ x1: number; y1: number; x2: number; y2: number }>(
    "capture:region-selected",
    async (event) => {
      const { x1, y1, x2, y2 } = event.payload;
      if (Math.abs(x2 - x1) < MIN_SELECTION || Math.abs(y2 - y1) < MIN_SELECTION) {
        await finish();
        return;
      }
      try {
        const image = await captureRegion(x1, y1, x2, y2);
        await handleNewCapture(image);
      } finally {
        await finish();
      }
    },
  );
  const unlistenCancelled = await listen("capture:cancelled", finish);
}
