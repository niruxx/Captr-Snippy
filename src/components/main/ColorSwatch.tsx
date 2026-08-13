/** Small circular color/width selectors for the annotation toolbar - direct
 * port of widgets/color_dot.py's ColorSwatch/WidthSwatch. */
export function ColorSwatch({
  color,
  selected,
  onClick,
}: {
  color: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Color ${color}`}
      className="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center transition-transform duration-200 hover:scale-125 active:scale-95"
      style={{ transitionTimingFunction: "var(--ease-spring)" }}
    >
      <span
        className={`rounded-full border border-border transition-all duration-200 ${selected ? "h-4 w-4" : "h-3.5 w-3.5"}`}
        style={{
          backgroundColor: color,
          boxShadow: selected ? `0 0 0 2px var(--surface-strong), 0 0 0 3.5px var(--accent), 0 0 8px 1px var(--accent-glow-shadow)` : undefined,
        }}
      />
    </button>
  );
}

export function WidthSwatch({
  widthValue,
  selected,
  onClick,
}: {
  widthValue: number;
  selected: boolean;
  onClick: () => void;
}) {
  const dotSize = 2 * (2 + widthValue);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Stroke width ${widthValue}`}
      className="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center transition-transform duration-200 hover:scale-125 active:scale-95"
      style={{ transitionTimingFunction: "var(--ease-spring)" }}
    >
      <span
        className={`rounded-full transition-colors ${selected ? "bg-accent" : "bg-text-secondary"}`}
        style={{
          width: dotSize,
          height: dotSize,
          boxShadow: selected ? `0 0 0 2px var(--surface-strong), 0 0 0 3.5px var(--accent)` : undefined,
        }}
      />
    </button>
  );
}
