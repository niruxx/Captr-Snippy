import { create } from "zustand";
import { getSettings, saveSettings } from "../lib/ipc";
import type { Settings } from "../lib/types";

interface SettingsState {
  settings: Settings | null;
  loaded: boolean;
  load: () => Promise<void>;
  /** Merges a partial update, persists it, and updates local state - the
   * same "mutate then explicitly save" flow settings_view.py used. */
  update: (patch: Partial<Settings>) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: null,
  loaded: false,

  async load() {
    const settings = await getSettings();
    set({ settings, loaded: true });
  },

  async update(patch) {
    const current = get().settings;
    if (!current) return;
    const next = { ...current, ...patch };
    set({ settings: next });
    await saveSettings(next);
  },
}));
