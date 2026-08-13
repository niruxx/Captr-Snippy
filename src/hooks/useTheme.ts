import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

/** Live-syncs the OS light/dark theme onto a `dark` class on <html>, driving
 * every Tailwind `dark:`-aware utility. Direct replacement for theme.py's
 * `system_dark_mode()` registry read - Tauri's theme()/onThemeChanged()
 * already track the same OS value and update live with no polling. */
export function useTheme() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const win = getCurrentWindow();
    let unlisten: (() => void) | undefined;

    win.theme().then((theme) => setDark(theme === "dark"));
    win.onThemeChanged(({ payload }) => setDark(payload === "dark")).then((fn) => {
      unlisten = fn;
    });

    return () => unlisten?.();
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return dark;
}
