import { THEMES } from "../../lib/themes";

/** A grid of theme preview cards - shared between Settings → Appearance
 * and the first-run onboarding flow, so both pick from the exact same
 * registry and never drift out of sync. */
export function ThemePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {THEMES.map((theme) => {
        const selected = theme.id === value;
        return (
          <button
            key={theme.id}
            type="button"
            onClick={() => onChange(theme.id)}
            className="group flex cursor-pointer flex-col items-center gap-2 rounded-2xl border p-3 text-center transition-all duration-200"
            style={{
              borderColor: selected ? "var(--accent)" : "var(--border)",
              background: selected ? "var(--surface-strong)" : "var(--surface)",
              boxShadow: selected ? "0 0 0 3px var(--accent-glow-shadow)" : "none",
              transitionTimingFunction: "var(--ease-spring)",
            }}
          >
            <span
              className="h-12 w-full rounded-xl transition-transform duration-200 group-hover:scale-[1.03]"
              style={{
                background: `linear-gradient(135deg, ${theme.swatch[0]}, ${theme.swatch[1]})`,
                transitionTimingFunction: "var(--ease-spring)",
              }}
            />
            <span className="text-sm font-semibold">{theme.name}</span>
          </button>
        );
      })}
    </div>
  );
}
