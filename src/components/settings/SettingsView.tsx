import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { isEnabled as isAutostartEnabled, enable as enableAutostart, disable as disableAutostart } from "@tauri-apps/plugin-autostart";
import { useSettingsStore } from "../../state/settingsStore";
import { useToastStore } from "../../state/toastStore";
import {
  EXPORT_FORMATS,
  HISTORY_LIMIT_PRESETS,
  RECORD_FPS_PRESETS,
  VIDEO_FORMATS,
} from "../../lib/constants";
import { getHdrStatus, getMonitors } from "../../lib/ipc";
import type { DisplayColorStatus, MonitorRect } from "../../lib/types";
import { Button } from "../buttons/Button";
import { Card, SectionLabel } from "./Card";
import { SegmentedControl } from "./SegmentedControl";
import { ThemePicker } from "./ThemePicker";
import { ToggleSwitch } from "./ToggleSwitch";
import { getTheme } from "../../lib/themes";

export function SettingsView({ onBack }: { onBack: () => void }) {
  const { settings, update } = useSettingsStore();
  const [monitors, setMonitors] = useState<MonitorRect[]>([]);
  const [hdrStatus, setHdrStatus] = useState<DisplayColorStatus[]>([]);
  const [autostart, setAutostart] = useState(false);

  useEffect(() => {
    getMonitors().then(setMonitors);
    getHdrStatus().then(setHdrStatus);
    // The OS registration itself (not settings.json) is the source of
    // truth here, so it's read fresh rather than persisted/mirrored -
    // avoids the two ever silently drifting apart.
    isAutostartEnabled().then(setAutostart).catch(() => {});
  }, []);

  async function toggleAutostart(next: boolean) {
    try {
      if (next) {
        await enableAutostart();
      } else {
        await disableAutostart();
      }
      setAutostart(next);
    } catch (err) {
      useToastStore.getState().show(`Failed to update startup setting: ${err}`);
    }
  }

  const historyOptions = useMemo(() => {
    if (!settings) return HISTORY_LIMIT_PRESETS.map(String);
    const values = new Set<number>(HISTORY_LIMIT_PRESETS);
    values.add(settings.history_limit);
    return Array.from(values).sort((a, b) => a - b).map(String);
  }, [settings?.history_limit]);

  const hdrStatusText = (() => {
    if (hdrStatus.length === 0) return "HDR status: unknown on this system/Windows version.";
    const on = hdrStatus.filter((s) => s.enabled).length;
    if (on > 0) return `HDR status: ${on} of ${hdrStatus.length} display(s) currently in HDR mode.`;
    return `HDR status: all ${hdrStatus.length} display(s) are in SDR mode.`;
  })();

  const fpsOptions = useMemo(() => {
    if (!settings) return RECORD_FPS_PRESETS.map(String);
    const values = new Set<number>(RECORD_FPS_PRESETS);
    values.add(settings.record_fps);
    return Array.from(values).sort((a, b) => a - b).map(String);
  }, [settings?.record_fps]);

  // "Entire desktop" + one entry per monitor + "Choose window" - direct
  // port of settings_view.py's _build_recording_section() source list.
  const sourceOptions = useMemo(() => {
    const values = ["all", ...monitors.map((_, i) => `monitor:${i}`), "window"];
    const labels: Record<string, string> = {
      all: "Entire desktop",
      window: "Choose window",
    };
    monitors.forEach((_, i) => {
      labels[`monitor:${i}`] = `Monitor ${i + 1}`;
    });
    return { values, labels };
  }, [monitors]);

  if (!settings) return null;

  async function chooseQuickSaveDir() {
    const chosen = await open({
      directory: true,
      defaultPath: settings!.quick_save_dir,
      title: "Quick save folder",
    });
    if (typeof chosen === "string") {
      update({ quick_save_dir: chosen });
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 pt-4 pb-3">
        <Button
          variant="glass"
          pill
          icon="back"
          iconSize={16}
          width={36}
          height={36}
          aria-label="Back"
          title="Back"
          onClick={onBack}
        />
        <h1 className="text-lg font-bold tracking-tight">Settings</h1>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 pb-5">
        {/* -- Appearance -- */}
        <section>
          <SectionLabel>Appearance</SectionLabel>
          <Card>
            <span>Theme</span>
            <ThemePicker value={settings.theme} onChange={(theme) => update({ theme })} />
            <p className="text-text-secondary">{getTheme(settings.theme).description}</p>
          </Card>
        </section>

        {/* -- Export -- */}
        <section>
          <SectionLabel>Export</SectionLabel>
          <Card>
            <span>Image format</span>
            <SegmentedControl
              options={EXPORT_FORMATS}
              value={settings.export_format}
              onChange={(v) => update({ export_format: v })}
            />
            <div className="mt-2 flex items-center justify-between">
              <span>Quality</span>
              <span className="text-text-secondary">{settings.quality}</span>
            </div>
            <input
              type="range"
              min={40}
              max={100}
              value={settings.quality}
              onChange={(e) => update({ quality: Number(e.target.value) })}
              className="w-full accent-accent"
            />
            <p className="text-text-secondary">Quality applies to JPEG and WEBP exports.</p>
          </Card>
        </section>

        {/* -- General -- */}
        <section>
          <SectionLabel>General</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <div className="flex items-center justify-between">
                <span>Copy after capture</span>
                <ToggleSwitch
                  checked={settings.auto_copy}
                  onChange={(v) => update({ auto_copy: v })}
                />
              </div>
              <p className="text-text-secondary">
                Puts every new capture on the clipboard automatically.
              </p>
            </Card>
            <Card>
              <div className="flex items-center justify-between">
                <span>Quick save folder</span>
                <Button
                  variant="glass"
                  width={68}
                  height={26}
                  className="text-xs"
                  onClick={chooseQuickSaveDir}
                >
                  Change
                </Button>
              </div>
              <p className="wrap-anywhere text-text-secondary">{settings.quick_save_dir}</p>
            </Card>
            <Card>
              <div className="flex items-center justify-between">
                <span>Capture sound</span>
                <ToggleSwitch
                  checked={settings.capture_sound}
                  onChange={(v) => update({ capture_sound: v })}
                />
              </div>
              <p className="text-text-secondary">Plays a shutter click on every new capture.</p>
            </Card>
            <Card>
              <span>History size</span>
              <SegmentedControl
                options={historyOptions}
                value={String(settings.history_limit)}
                onChange={(v) => update({ history_limit: Number(v) })}
                segWidth={40}
              />
              <p className="text-text-secondary">Thumbnails kept in the history rail.</p>
            </Card>
            <Card>
              <div className="flex items-center justify-between">
                <span>Launch at startup</span>
                <ToggleSwitch checked={autostart} onChange={toggleAutostart} />
              </div>
              <p className="text-text-secondary">Starts Captr automatically when you sign in.</p>
            </Card>
            <Card>
              <div className="flex items-center justify-between">
                <span>Minimize to tray</span>
                <ToggleSwitch
                  checked={settings.close_to_tray}
                  onChange={(v) => update({ close_to_tray: v })}
                />
              </div>
              <p className="text-text-secondary">
                Closing the window hides it to the tray instead of quitting, so hotkeys and
                recordings keep working. Quit from the tray icon to exit for real.
              </p>
            </Card>
          </div>
        </section>

        {/* -- Screen Recording -- */}
        <section>
          <SectionLabel>Screen Recording</SectionLabel>
          <Card>
            <span>Video format</span>
            <SegmentedControl
              options={VIDEO_FORMATS}
              value={settings.video_format}
              onChange={(v) => update({ video_format: v })}
              segWidth={56}
            />
            <span className="mt-2">Frame rate</span>
            <SegmentedControl
              options={fpsOptions}
              value={String(settings.record_fps)}
              onChange={(v) => update({ record_fps: Number(v) })}
              segWidth={46}
            />
            <span className="mt-2">Record source</span>
            <SegmentedControl
              options={sourceOptions.values}
              value={sourceOptions.values.includes(settings.record_source) ? settings.record_source : "all"}
              onChange={(v) => update({ record_source: v })}
              segWidth={96}
              labels={sourceOptions.labels}
            />
            <div className="mt-2 flex items-center justify-between">
              <span>Show cursor in recordings</span>
              <ToggleSwitch
                checked={settings.record_cursor}
                onChange={(v) => update({ record_cursor: v })}
              />
            </div>
            <p className="text-text-secondary">
              Match your display's refresh rate for the smoothest capture (higher rates need
              more CPU and disk space). "Choose window" asks which one each time you hit
              Record and follows it if it moves or resizes. Ctrl+Alt+R starts/stops,
              Ctrl+Alt+P pauses/resumes, from anywhere.
            </p>
          </Card>
        </section>

        {/* -- HDR Capture -- */}
        <section>
          <SectionLabel>HDR Capture</SectionLabel>
          <Card>
            <div className="flex items-center justify-between">
              <span>Correct washed-out HDR captures</span>
              <ToggleSwitch
                checked={settings.hdr_tone_map}
                onChange={(v) => update({ hdr_tone_map: v })}
              />
            </div>
            <p className="text-text-secondary">
              Screenshots of HDR content can look dim or washed out, because capture APIs only
              ever see the SDR-referenced blend Windows composites, not the brightness boost
              the display itself applies. When on, new captures taken while a display is in
              HDR mode get a brightness/contrast lift to compensate (a heuristic, not a
              physically accurate tone-map).
            </p>
            <p className="text-text-secondary">{hdrStatusText}</p>
          </Card>
        </section>

        {/* -- Shortcuts -- */}
        <section>
          <SectionLabel>Shortcuts</SectionLabel>
          <Card>
            <p className="text-text-secondary">Ctrl+N region · Ctrl+F full screen · Ctrl+Z undo</p>
          </Card>
        </section>
      </div>
    </div>
  );
}
