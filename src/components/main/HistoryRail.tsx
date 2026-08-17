import { useCaptureStore } from "../../state/captureStore";

const THUMB_SIZE = 64;

/** Grid of recent captures - Google Photos' signature pattern (a compact
 * row of it, not a full library) instead of the previous horizontal strip.
 * Collapses to nothing when history is empty. */
export function HistoryRail() {
  const history = useCaptureStore((s) => s.history);
  const historyIndex = useCaptureStore((s) => s.historyIndex);
  const selectCapture = useCaptureStore((s) => s.selectCapture);

  if (history.length === 0) return null;

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-center gap-2 px-5 py-2.5">
      {history.map((image, i) => {
        const selected = i === historyIndex;
        return (
          <button
            key={image.data_url.slice(-32) + i}
            type="button"
            onClick={() => selectCapture(i)}
            aria-label={`Capture ${i + 1}`}
            className="animate-pop-in shrink-0 cursor-pointer overflow-hidden rounded-xl bg-border-soft transition-all duration-150"
            style={{
              width: THUMB_SIZE,
              height: THUMB_SIZE,
              outline: selected ? "2.5px solid var(--accent)" : "1px solid var(--border)",
              outlineOffset: selected ? -2.5 : -1,
              boxShadow: selected ? "0 2px 8px -1px var(--accent-glow-shadow)" : "none",
              animationDelay: `${i * 30}ms`,
            }}
          >
            <img src={image.data_url} alt="" className="h-full w-full object-cover" />
          </button>
        );
      })}
    </div>
  );
}
