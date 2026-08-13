// Save As / Quick Save / Copy to clipboard - direct port of
// main_window.py's save_screenshot()/quick_save()/_write_image()/
// copy_to_clipboard().
import { save } from "@tauri-apps/plugin-dialog";
import { writeImage } from "@tauri-apps/plugin-clipboard-manager";
import { Image as TauriImage } from "@tauri-apps/api/image";
import { useCaptureStore } from "../state/captureStore";
import { useSettingsStore } from "../state/settingsStore";
import { useToastStore } from "../state/toastStore";
import { EXPORT_EXTENSIONS } from "./constants";
import { dataUrlToImageData, timestampForFilename } from "./imageUtils";
import { saveImage } from "./ipc";

function toast(message: string) {
  useToastStore.getState().show(message);
}

async function currentImageData() {
  const { screenshot } = useCaptureStore.getState();
  if (!screenshot) return null;
  return dataUrlToImageData(screenshot.data_url);
}

export async function saveAs() {
  const settings = useSettingsStore.getState().settings;
  const imageData = await currentImageData();
  if (!settings || !imageData) {
    toast("Capture a screenshot first");
    return;
  }

  const ext = EXPORT_EXTENSIONS[settings.export_format];
  const path = await save({
    defaultPath: `snippet_${timestampForFilename()}.${ext}`,
    filters: [{ name: settings.export_format, extensions: [ext] }],
  });
  if (!path) return;

  try {
    await saveImage(imageData.width, imageData.height, imageData.data, settings.export_format, settings.quality, path);
    toast(`Saved as ${settings.export_format}`);
  } catch (err) {
    toast(`Failed to save: ${err}`);
  }
}

export async function quickSave() {
  const settings = useSettingsStore.getState().settings;
  const imageData = await currentImageData();
  if (!settings || !imageData) {
    toast("Capture a screenshot first");
    return;
  }

  const ext = EXPORT_EXTENSIONS[settings.export_format];
  const separator = settings.quick_save_dir.includes("/") ? "/" : "\\";
  const path = `${settings.quick_save_dir}${separator}snippet_${timestampForFilename()}.${ext}`;

  try {
    await saveImage(imageData.width, imageData.height, imageData.data, settings.export_format, settings.quality, path);
    toast(`Saved to ${settings.quick_save_dir}`);
  } catch (err) {
    toast(`Failed to save: ${err}`);
  }
}

/** Writes the current capture's pixels to the OS clipboard - no toast, no
 * capture-presence check, so both the manual "Copy" action and the silent
 * auto-copy-on-capture path can share it and layer their own messaging. */
export async function writeCurrentToClipboard(): Promise<boolean> {
  const imageData = await currentImageData();
  if (!imageData) return false;
  // getImageData() returns a Uint8ClampedArray, which misses Tauri's binary
  // IPC fast path (only Uint8Array/ArrayBuffer qualify) and falls back to a
  // slow, invalid map serialization - same class of bug as saveImage() in
  // ipc.ts, fixed the same way.
  const rgba = new Uint8Array(imageData.data.buffer, imageData.data.byteOffset, imageData.data.byteLength);
  const image = await TauriImage.new(rgba, imageData.width, imageData.height);
  await writeImage(image);
  return true;
}

export async function copyToClipboard() {
  try {
    const copied = await writeCurrentToClipboard();
    toast(copied ? "Copied to clipboard" : "Capture a screenshot first");
  } catch (err) {
    toast(`Failed to copy: ${err}`);
  }
}
