import { useToastStore } from "../../state/toastStore";

export function Toast() {
  const message = useToastStore((s) => s.message);

  return (
    <div
      className={`pointer-events-none absolute bottom-7 left-1/2 z-50 -translate-x-1/2 rounded-full border border-highlight-edge bg-surface-strong/95 px-5 py-3 text-sm font-semibold whitespace-nowrap shadow-xl shadow-black/20 backdrop-blur-xl transition-all duration-300 ${
        message ? "translate-y-0 scale-100 opacity-100" : "translate-y-3 scale-95 opacity-0"
      }`}
      style={{ transitionTimingFunction: "var(--ease-spring)" }}
    >
      {message}
    </div>
  );
}
