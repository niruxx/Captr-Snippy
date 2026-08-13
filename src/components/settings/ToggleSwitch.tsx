/** Sliding-knob toggle - direct port of widgets/switch.py. */
export function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-10 shrink-0 cursor-pointer rounded-full border transition-all duration-200 ${
        checked
          ? "border-accent bg-linear-to-r from-accent to-accent-glow shadow-[0_0_10px_-1px_var(--accent-glow-shadow)]"
          : "border-border bg-border-soft"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
        style={{ transitionTimingFunction: "var(--ease-spring)" }}
      />
    </button>
  );
}
