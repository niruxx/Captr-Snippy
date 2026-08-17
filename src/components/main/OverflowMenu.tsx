import { useEffect, useRef, useState } from "react";
import { Button } from "../buttons/Button";
import { useCaptureStore } from "../../state/captureStore";
import { saveAs, quickSave, copyToClipboard } from "../../lib/exportActions";

/** The "···" overflow menu for less-central actions - direct port of
 * main_view.py's `_show_overflow_menu()`. */
export function OverflowMenu() {
  const [open, setOpen] = useState(false);
  const removeCurrent = useCaptureStore((s) => s.removeCurrent);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickAway(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    window.addEventListener("mousedown", onClickAway);
    return () => window.removeEventListener("mousedown", onClickAway);
  }, [open]);

  function run(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="plain"
        pill
        icon="more"
        iconSize={17}
        width={34}
        height={34}
        aria-label="More actions"
        title="More actions"
        onClick={() => setOpen((v) => !v)}
      />
      {open && (
        <div className="absolute top-full right-0 z-50 mt-2 w-56 origin-top-right animate-pop-in rounded-2xl border border-border bg-surface-strong p-1.5 shadow-xl shadow-black/15">
          <MenuItem label="Save As…" hint="Ctrl+S" onClick={() => run(saveAs)} />
          <MenuItem label="Quick Save" hint="Ctrl+Q" onClick={() => run(quickSave)} />
          <MenuItem label="Copy to Clipboard" hint="Ctrl+C" onClick={() => run(copyToClipboard)} />
          <div className="my-1 h-px bg-border-soft" />
          <MenuItem label="Remove Capture" hint="Del" onClick={() => run(removeCurrent)} />
        </div>
      )}
    </div>
  );
}

function MenuItem({ label, hint, onClick }: { label: string; hint: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-hover"
    >
      <span>{label}</span>
      <span className="text-text-tertiary">{hint}</span>
    </button>
  );
}
