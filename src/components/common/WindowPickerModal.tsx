import { useState } from "react";
import { useWindowPickerStore } from "../../state/windowPickerStore";

/**
 * "Choose a window to record" - direct port of views/window_picker.py's
 * WindowPickerDialog, as an in-app modal rather than a separate native
 * dialog (it doesn't need overlay/always-on-top/capture-exclusion, unlike
 * the capture overlay or record bar, so a separate Tauri window would be
 * pure overhead here).
 */
export function WindowPickerModal() {
  const { open, windows, choose, cancel } = useWindowPickerStore();
  const [selected, setSelected] = useState(0);

  if (!open) return null;

  function confirm() {
    const entry = windows[selected];
    if (entry) choose(entry.hwnd);
  }

  return (
    <div className="absolute inset-0 z-50 flex animate-pop-in items-center justify-center bg-black/50">
      <div className="flex max-h-[80%] w-80 flex-col overflow-hidden rounded-2xl border border-border bg-surface-strong shadow-2xl shadow-black/30">
        <div className="px-4 pt-4 pb-2 text-sm font-semibold">Choose a window to record</div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {windows.length === 0 && (
            <p className="px-2 py-4 text-sm text-text-secondary">No windows available.</p>
          )}
          {windows.map((entry, i) => (
            <button
              key={entry.hwnd}
              type="button"
              onClick={() => setSelected(i)}
              onDoubleClick={confirm}
              className={`block w-full cursor-pointer truncate rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                i === selected ? "bg-accent text-accent-text" : "hover:bg-hover"
              }`}
            >
              {entry.title}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border-soft px-4 py-3">
          <button
            type="button"
            onClick={cancel}
            className="cursor-pointer rounded-lg px-3 py-1.5 text-sm transition-colors hover:bg-hover"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={windows.length === 0}
            className="cursor-pointer rounded-lg bg-linear-to-br from-accent to-accent-glow px-3 py-1.5 text-sm font-semibold text-accent-text shadow-[0_2px_10px_-2px_var(--accent-glow-shadow)] transition-all active:scale-95 disabled:opacity-40 disabled:active:scale-100"
          >
            Record
          </button>
        </div>
      </div>
    </div>
  );
}
