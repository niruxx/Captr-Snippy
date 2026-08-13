/** Theme registry - each entry is an accent-color palette plus an animated
 * background "flavor", applied together via CSS custom properties on
 * `<html>` (see `hooks/useTheme.ts`) so every already-`var(--accent)`-based
 * surface in the app re-themes for free, titlebar included - the brand
 * dot, primary buttons, selected-state glows, etc. never reference a literal
 * color, only these tokens. Independent of the light/dark mode toggle,
 * which stays driven by the OS setting exactly as before. */

export type ThemeId = "classic" | "aurora" | "snowfall" | "sunset";
export type BackgroundKind = "none" | "aurora" | "snowfall" | "sunset";

export interface ThemeDefinition {
  id: ThemeId;
  name: string;
  description: string;
  background: BackgroundKind;
  /** `null` means "don't override - let the existing light/dark :root/.dark
   * tokens apply", which is what makes "classic" the exact original look. */
  accent: { accent: string; accentHover: string; accentGlow: string; accentGlowShadow: string } | null;
  /** 2-3 preview colors for the swatch shown in Settings/onboarding. */
  swatch: string[];
}

export const THEMES: ThemeDefinition[] = [
  {
    id: "classic",
    name: "Classic",
    description: "The original violet-on-glass look, no animated background.",
    background: "none",
    accent: null,
    swatch: ["#8c7cff", "#ff8cdc"],
  },
  {
    id: "aurora",
    name: "Aurora",
    description: "Drifting emerald-and-violet aurora blobs behind the glass.",
    background: "aurora",
    accent: {
      accent: "#4ee6b8",
      accentHover: "#6cf0c8",
      accentGlow: "#7c8cff",
      accentGlowShadow: "rgb(78 230 184 / 45%)",
    },
    swatch: ["#4ee6b8", "#7c8cff"],
  },
  {
    id: "snowfall",
    name: "Snowfall",
    description: "Gentle falling snow over a cool midnight-blue sky.",
    background: "snowfall",
    accent: {
      accent: "#5ca8e7",
      accentHover: "#7cbdf0",
      accentGlow: "#a8e7ff",
      accentGlowShadow: "rgb(92 168 231 / 45%)",
    },
    swatch: ["#5ca8e7", "#a8e7ff"],
  },
  {
    id: "sunset",
    name: "Sunset",
    description: "Warm drifting embers of orange, rose, and amber.",
    background: "sunset",
    accent: {
      accent: "#e78c5c",
      accentHover: "#f0a378",
      accentGlow: "#ff6c8c",
      accentGlowShadow: "rgb(231 140 92 / 45%)",
    },
    swatch: ["#e78c5c", "#ff6c8c"],
  },
];

export function getTheme(id: string): ThemeDefinition {
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}
