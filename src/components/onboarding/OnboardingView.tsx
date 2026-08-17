import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useSettingsStore } from "../../state/settingsStore";
import { Button } from "../buttons/Button";
import { Icon } from "../icons/Icon";

const STEP_COUNT = 2;

/** First-run welcome flow - shown once, gated on `settings.onboarding_complete`
 * (see App.tsx). Finishing (or skipping) just flips that flag through the
 * normal settings store, same persistence path as every other setting, so
 * there's no separate "first run" storage to keep in sync. */
export function OnboardingView() {
  const { settings, update } = useSettingsStore();
  const [step, setStep] = useState(0);

  if (!settings) return null;

  function finish() {
    update({ onboarding_complete: true });
  }

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
    <div className="flex h-full flex-col items-center justify-center gap-8 px-10 py-8 text-center">
      <div key={step} className="flex w-full max-w-md animate-capture-in flex-col items-center gap-5">
        {step === 0 && <WelcomeStep />}
        {step === 1 && (
          <FolderStep dir={settings.quick_save_dir} onChoose={chooseQuickSaveDir} />
        )}
      </div>

      <div className="flex items-center gap-2">
        {Array.from({ length: STEP_COUNT }).map((_, i) => (
          <span
            key={i}
            className="h-1.5 rounded-full transition-all duration-300"
            style={{
              width: i === step ? 20 : 6,
              background: i === step ? "var(--accent)" : "var(--border)",
              transitionTimingFunction: "var(--ease-spring)",
            }}
          />
        ))}
      </div>

      <div className="flex items-center gap-2">
        {step > 0 && (
          <Button variant="glass" onClick={() => setStep((s) => s - 1)} className="px-5">
            Back
          </Button>
        )}
        {step < STEP_COUNT - 1 ? (
          <Button variant="primary" onClick={() => setStep((s) => s + 1)} className="px-6">
            Continue
          </Button>
        ) : (
          <Button variant="primary" onClick={finish} className="px-6">
            Get Started
          </Button>
        )}
        {step === 0 && (
          <Button variant="plain" onClick={finish} className="px-4 text-text-secondary">
            Skip
          </Button>
        )}
      </div>
    </div>
  );
}

function WelcomeStep() {
  return (
    <>
      <div className="animate-drift rounded-full bg-linear-to-br from-accent/20 to-accent-glow/20 p-6">
        <Icon name="fullscreen" size={36} className="text-accent" />
      </div>
      <h1 className="text-2xl font-bold tracking-tight">Welcome to Captr</h1>
      <p className="text-text-secondary">
        Capture, annotate, and record your screen in seconds. Let's get a couple of things set
        up before your first snip.
      </p>
    </>
  );
}

function FolderStep({ dir, onChoose }: { dir: string; onChoose: () => void }) {
  return (
    <>
      <div className="rounded-full bg-linear-to-br from-accent/20 to-accent-glow/20 p-6">
        <Icon name="plus" size={36} className="text-accent" />
      </div>
      <h1 className="text-2xl font-bold tracking-tight">Where should Quick Save go?</h1>
      <p className="text-text-secondary">
        Quick Save (<kbd className="rounded bg-hover px-1.5 py-0.5 text-xs">Ctrl+Q</kbd>) drops
        every capture here instantly, no dialog.
      </p>
      <div className="flex w-full items-center gap-2 rounded-2xl border border-border bg-surface p-3">
        <p className="wrap-anywhere flex-1 text-left text-sm text-text-secondary">{dir}</p>
        <Button variant="glass" width={80} height={32} className="text-xs" onClick={onChoose}>
          Change
        </Button>
      </div>
    </>
  );
}
