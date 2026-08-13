import { useEffect, useState } from "react";
import { Button } from "../buttons/Button";
import { SegmentedControl } from "../settings/SegmentedControl";
import { PreviewCanvas } from "./PreviewCanvas";
import { ContextualToolbar } from "./ContextualToolbar";
import { HistoryRail } from "./HistoryRail";
import { OverflowMenu } from "./OverflowMenu";
import { useCaptureStore } from "../../state/captureStore";
import { useRecordingStore } from "../../state/recordingStore";
import { startFullscreenCapture, startRegionCapture } from "../../lib/captureActions";
import { copyToClipboard, quickSave, saveAs } from "../../lib/exportActions";
import { toggleRecording } from "../../lib/recordingActions";

const DELAY_OPTIONS = ["0s", "3s", "10s"] as const;

export function MainView({ onOpenSettings }: { onOpenSettings: () => void }) {
  const screenshot = useCaptureStore((s) => s.screenshot);
  const undo = useCaptureStore((s) => s.undo);
  const removeCurrent = useCaptureStore((s) => s.removeCurrent);
  const isRecording = useRecordingStore((s) => s.isRecording);
  const [delay, setDelay] = useState<(typeof DELAY_OPTIONS)[number]>("0s");
  const [busy, setBusy] = useState(false);

  const delayMs = Number(delay.replace("s", "")) * 1000;

  async function handleSnip() {
    setBusy(true);
    try {
      await startRegionCapture(delayMs);
    } finally {
      setBusy(false);
    }
  }

  async function handleFullscreen() {
    setBusy(true);
    try {
      await startFullscreenCapture(delayMs);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!e.ctrlKey) {
        if (e.key === "Delete") removeCurrent();
        if (e.key === "PrintScreen") handleSnip();
        return;
      }
      switch (e.key.toLowerCase()) {
        case "n":
          e.preventDefault();
          handleSnip();
          break;
        case "f":
          e.preventDefault();
          handleFullscreen();
          break;
        case "z":
          e.preventDefault();
          undo();
          break;
        case "s":
          e.preventDefault();
          saveAs();
          break;
        case "q":
          e.preventDefault();
          quickSave();
          break;
        case "c":
          e.preventDefault();
          copyToClipboard();
          break;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [undo, removeCurrent, delayMs]);

  return (
    <div className="flex h-full flex-col">
      {/* Nothing but the titlebar sits above the preview now - no status
       * strip, no shortcuts hint (moved to Settings) - so the preview gets
       * the full space. A little extra top padding fills in for the row
       * that used to be here. */}
      <div className="relative min-h-0 flex-1 overflow-hidden px-5 pt-3 pb-2">
        <PreviewCanvas />
        {screenshot && <ContextualToolbar />}
      </div>

      <HistoryRail />

      {/* Bottom action row: the capture dock (the tool's primary surface)
       * centered via a 3-column grid - the empty first column keeps the
       * center column mathematically centered regardless of the settings
       * cluster's width in the third, without needing a placeholder brand
       * label the way the top-docked version did. z-20 + relative: the
       * settings cluster uses backdrop-blur, which (like any non-none
       * filter) establishes its own CSS stacking context - without an
       * explicit z-index here, that context and PreviewCanvas's own
       * backdrop-blur'd stacking context become same-level siblings
       * ordered by DOM position, and since the overflow menu now opens
       * *upward* over the preview, it needs to explicitly outrank it. */}
      <div className="relative z-20 grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-5 pt-2 pb-2">
        <div />

        <div className="flex animate-pop-in items-center gap-1.5 justify-self-center rounded-dock border border-highlight-edge bg-surface-strong/90 p-1.5 shadow-lg shadow-black/10 backdrop-blur-xl">
          <Button variant="primary" pill icon="plus" iconSize={14} height={36} className="px-4" disabled={busy} onClick={handleSnip}>
            Snip region
          </Button>
          <Button
            variant="plain"
            pill
            icon="fullscreen"
            iconSize={15}
            width={36}
            height={36}
            disabled={busy}
            aria-label="Full screen capture"
            title="Full screen capture (Ctrl+F)"
            onClick={handleFullscreen}
          />
          <Button
            variant="plain"
            pill
            icon="record"
            iconSize={12}
            iconColorClassName={isRecording ? "text-white" : "text-error"}
            width={104}
            height={36}
            className={isRecording ? "bg-error text-white hover:bg-error" : ""}
            title={isRecording ? "Stop screen recording (Ctrl+Alt+R)" : "Start screen recording (Ctrl+Alt+R)"}
            onClick={() => toggleRecording()}
          >
            {isRecording && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />}
            {isRecording ? "Stop" : "Record"}
          </Button>
          <div className="mx-0.5 h-6 w-px shrink-0 bg-border-soft" />
          <SegmentedControl options={DELAY_OPTIONS} value={delay} onChange={setDelay} segWidth={36} height={28} />
        </div>

        <div className="flex items-center gap-0.5 justify-self-end rounded-dock border border-highlight-edge bg-surface-strong/80 p-1 shadow-md shadow-black/10 backdrop-blur-xl">
          <OverflowMenu />
          <Button
            variant="plain"
            pill
            icon="settings"
            iconSize={16}
            width={32}
            height={32}
            aria-label="Settings"
            title="Settings"
            onClick={onOpenSettings}
          />
        </div>
      </div>

      <p className="pb-2 text-center text-[10px] tracking-wide text-text-tertiary/70">
        - niruxxdaboi -
      </p>
    </div>
  );
}
