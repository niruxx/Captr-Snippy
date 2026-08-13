import { useState } from "react";
import { MainView } from "../main/MainView";
import { SettingsView } from "../settings/SettingsView";

type View = "main" | "settings";

/** Two absolutely-stacked panes that slide past each other via a CSS
 * transform transition - direct behavioral port of widgets/slide_stack.py
 * (main slides left as Settings enters from the right, and back). */
export function SlidePanel() {
  const [view, setView] = useState<View>("main");

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        className={`absolute inset-0 transition-transform duration-300 ${
          view === "main" ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ transitionTimingFunction: "var(--ease-smooth)" }}
      >
        <MainView onOpenSettings={() => setView("settings")} />
      </div>
      <div
        className={`absolute inset-0 transition-transform duration-300 ${
          view === "settings" ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ transitionTimingFunction: "var(--ease-smooth)" }}
      >
        <SettingsView onBack={() => setView("main")} />
      </div>
    </div>
  );
}
