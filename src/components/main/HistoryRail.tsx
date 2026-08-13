import { useCaptureStore } from "../../state/captureStore";

const THUMB_W = 96;
const THUMB_H = 60;

/** Thumbnail strip of recent captures - direct port of
 * views/history_rail.py. Collapses to nothing when history is empty. */
export function HistoryRail() {
  const history = useCaptureStore((s) => s.history);
  const historyIndex = useCaptureStore((s) => s.historyIndex);
  const selectCapture = useCaptureStore((s) => s.selectCapture);

  if (history.length === 0) return null;

  return (
    <div className="flex shrink-0 items-center justify-center gap-2.5 px-5 py-2.5">
      {history.map((image, i) => (
        <button
          key={image.data_url.slice(-32) + i}
          type="button"
          onClick={() => selectCapture(i)}
          aria-label={`Capture ${i + 1}`}
          className="animate-pop-in shrink-0 cursor-pointer overflow-hidden rounded-[10px] bg-transparent transition-all duration-200 hover:-translate-y-1"
          style={{
            width: THUMB_W,
            height: THUMB_H,
            border: i === historyIndex ? "2px solid var(--accent)" : "1px solid var(--border)",
            boxShadow:
              i === historyIndex
                ? "0 4px 14px -2px var(--accent-glow-shadow)"
                : "0 2px 6px -2px rgb(0 0 0 / 15%)",
            animationDelay: `${i * 40}ms`,
            transitionTimingFunction: "var(--ease-spring)",
          }}
        >
          <img src={image.data_url} alt="" className="h-full w-full object-contain" />
        </button>
      ))}
    </div>
  );
}
