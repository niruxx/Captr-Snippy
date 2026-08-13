import { useEffect, useState } from "react";
import { emit } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getRecordingStatus, pauseRecording, resumeRecording } from "../../lib/ipc";
import { Icon } from "../icons/Icon";

/**
 * Floating frameless HUD shown while recording - direct port of
 * widgets/record_bar.py's RecordControlBar. Runs in its own Tauri window
 * (excluded from screen capture on the Rust side via
 * `exclude_window_from_capture`), and polls recording status itself rather
 * than being pushed updates, since it's a separate JS context from the
 * main window. The Stop button hands control back to the main window via
 * an event (closing/re-showing windows across a window boundary is best
 * owned by the window doing the showing); Pause/Resume act directly since
 * they have no other window-side effects.
 */
export function RecordControlBar() {
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const [blinkOn, setBlinkOn] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const status = await getRecordingStatus();
        if (cancelled) return;
        if (!status.is_recording) {
          await getCurrentWindow().close();
          return;
        }
        setElapsed(status.elapsed_secs);
        setPaused(status.paused);
      } catch {
        // ignore transient poll failures
      }
    };
    tick();
    const statusTimer = setInterval(tick, 500);
    const blinkTimer = setInterval(() => setBlinkOn((v) => !v), 500);
    return () => {
      cancelled = true;
      clearInterval(statusTimer);
      clearInterval(blinkTimer);
    };
  }, []);

  async function handleTogglePause() {
    try {
      if (paused) {
        await resumeRecording();
        setPaused(false);
      } else {
        await pauseRecording();
        setPaused(true);
      }
    } catch {
      // recording may have already ended; the next poll tick will close us
    }
  }

  async function handleStop() {
    await emit("recordbar:stop-clicked");
  }

  const minutes = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const seconds = String(elapsed % 60).padStart(2, "0");
  const dotDim = paused || !blinkOn;

  return (
    <div
      data-tauri-drag-region="deep"
      className="flex h-screen w-screen animate-pop-in items-center gap-2 rounded-full border border-highlight-edge bg-surface-strong/90 px-4 shadow-xl shadow-black/30 backdrop-blur-xl"
    >
      <span
        className={`h-3 w-3 shrink-0 rounded-full transition-all duration-300 ${paused ? "bg-text-tertiary" : "bg-error"}`}
        style={{
          opacity: dotDim ? 0.35 : 1,
          boxShadow: paused ? "none" : "0 0 8px 1px var(--error)",
        }}
      />
      <span className="text-sm font-semibold tabular-nums text-text">
        {minutes}:{seconds}
      </span>
      <div className="flex-1" />
      <button
        type="button"
        onClick={handleTogglePause}
        aria-label={paused ? "Resume" : "Pause"}
        title={paused ? "Resume" : "Pause"}
        className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-text transition-all duration-150 hover:bg-hover active:scale-90"
      >
        <Icon name={paused ? "play" : "pause"} size={12} />
      </button>
      <button
        type="button"
        onClick={handleStop}
        aria-label="Stop"
        title="Stop"
        className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-text transition-all duration-150 hover:bg-error hover:text-white active:scale-90"
      >
        <Icon name="stop" size={12} />
      </button>
    </div>
  );
}
