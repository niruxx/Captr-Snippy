/** Sliding-pill segmented control - direct port of widgets/segmented.py. */
const PAD = 3;

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  segWidth = 72,
  height = 28,
  labels,
}: {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  segWidth?: number;
  height?: number;
  /** Display text per option, when it should differ from the option/value
   * itself (e.g. value "all" displayed as "Entire desktop"). */
  labels?: Partial<Record<T, string>>;
}) {
  const index = Math.max(0, options.indexOf(value));
  const thumbHeight = height - PAD * 2;

  return (
    <div
      className="relative shrink-0 rounded-full border border-border bg-black/5 dark:bg-white/5"
      style={{ width: segWidth * options.length + PAD * 2, height }}
    >
      <div
        className="absolute rounded-full bg-linear-to-br from-accent to-accent-glow shadow-[0_2px_8px_-1px_var(--accent-glow-shadow)] transition-transform duration-250"
        style={{
          width: segWidth,
          height: thumbHeight,
          top: PAD,
          left: PAD,
          transform: `translateX(${index * segWidth}px)`,
          transitionTimingFunction: "var(--ease-spring)",
        }}
      />
      <div className="relative flex h-full">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={`flex-1 cursor-pointer text-sm transition-colors duration-200 ${
              opt === value ? "font-semibold text-accent-text" : "text-text-secondary hover:text-text"
            }`}
          >
            {labels?.[opt] ?? opt}
          </button>
        ))}
      </div>
    </div>
  );
}
