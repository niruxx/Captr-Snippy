import { useEffect } from "react";
import { WindowFrame } from "./components/layout/WindowFrame";
import { TitleBar } from "./components/layout/TitleBar";
import { SlidePanel } from "./components/layout/SlidePanel";
import { Toast } from "./components/common/Toast";
import { WindowPickerModal } from "./components/common/WindowPickerModal";
import { OnboardingView } from "./components/onboarding/OnboardingView";
import { useTheme } from "./hooks/useTheme";
import { useAccentTheme } from "./hooks/useAccentTheme";
import { useRecordingEvents } from "./hooks/useRecordingEvents";
import { useSettingsStore } from "./state/settingsStore";

function App() {
  useTheme();
  useAccentTheme();
  useRecordingEvents();
  const load = useSettingsStore((s) => s.load);
  const loaded = useSettingsStore((s) => s.loaded);
  const onboardingComplete = useSettingsStore((s) => s.settings?.onboarding_complete);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <WindowFrame>
      <TitleBar />
      <div className="relative flex min-h-0 flex-1 flex-col">
        {loaded && (onboardingComplete ? <SlidePanel /> : <OnboardingView />)}
        <Toast />
        <WindowPickerModal />
      </div>
    </WindowFrame>
  );
}

export default App;
