import { useEffect } from "react";
import { useSettingsStore } from "../state/settingsStore";
import { getTheme } from "../lib/themes";

const OVERRIDE_VARS = ["--accent", "--accent-hover", "--accent-glow", "--accent-glow-shadow"] as const;

/** Applies the user's chosen theme's accent-color palette as inline CSS
 * custom properties on <html>, overriding the static :root/.dark values
 * from index.css. Every accent-driven surface in the app (buttons, the
 * titlebar's brand dot, selected-state glows, segmented-control thumbs...)
 * already reads `var(--accent)` etc., so this one override point re-themes
 * everything at once with no per-component work. "classic" has no accent
 * override (`theme.accent === null`), so switching back to it just clears
 * the inline properties and lets the original light/dark tokens re-apply. */
export function useAccentTheme() {
  const themeId = useSettingsStore((s) => s.settings?.theme);

  useEffect(() => {
    const root = document.documentElement.style;
    const theme = getTheme(themeId ?? "classic");
    if (!theme.accent) {
      OVERRIDE_VARS.forEach((v) => root.removeProperty(v));
      return;
    }
    root.setProperty("--accent", theme.accent.accent);
    root.setProperty("--accent-hover", theme.accent.accentHover);
    root.setProperty("--accent-glow", theme.accent.accentGlow);
    root.setProperty("--accent-glow-shadow", theme.accent.accentGlowShadow);
  }, [themeId]);
}
