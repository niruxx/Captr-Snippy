import { useToastStore } from "../../state/toastStore";

export function Toast() {
  const message = useToastStore((s) => s.message);

  return (
    // Material snackbars are a fixed dark pill regardless of the page's own
    // light/dark theme - deliberately not tracking --surface here.
    <div
      className={`pointer-events-none absolute bottom-7 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[#323232] px-4 py-3 text-sm font-medium whitespace-nowrap text-white shadow-lg shadow-black/30 transition-all duration-200 ${
        message ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
      }`}
      style={{ transitionTimingFunction: "var(--ease-smooth)" }}
    >
      {message}
    </div>
  );
}
