import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { AnimatedBackground } from "../background/AnimatedBackground";
import { useSettingsStore } from "../../state/settingsStore";

const FADE_MS = 200;

const WindowChromeContext = createContext<{ requestClose: () => void }>({
  requestClose: () => getCurrentWindow().close(),
});

export function useWindowChrome() {
  return useContext(WindowChromeContext);
}

/**
 * Rounded/transparent/fading root container for a Tauri window. The window
 * itself is created with `visible: false` (tauri.conf.json) so there's no
 * flash of unstyled content before the fade-in starts; `decorations:false`
 * + `transparent:true` means the webview compositor alpha-blends real
 * pixels around our CSS `rounded-window` corners, so - unlike the Qt build's
 * `rounded_mask.py` - no hand-built antialiased mask is needed here.
 * Close (titlebar button or OS-level Alt+F4/X) fades out before the window
 * actually closes, mirroring the Python build's closeEvent-then-fade.
 */
export function WindowFrame({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState(false);
  const closingRef = useRef(false);

  useEffect(() => {
    const win = getCurrentWindow();
    let unlistenClose: (() => void) | undefined;
    let unlistenFocus: (() => void) | undefined;

    win.show()
      .then(() => requestAnimationFrame(() => setVisible(true)))
      .catch((err) => console.error("window.show() failed:", err));
    win.onCloseRequested(async (event) => {
      if (closingRef.current) return;
      event.preventDefault();
      requestClose();
    }).then((fn) => {
      unlistenClose = fn;
    }).catch((err) => console.error("onCloseRequested() failed:", err));
    // The tray icon's "Show Captr" / left-click calls the native
    // window.show()+set_focus() directly from Rust, bypassing this
    // component entirely - without this, `visible` would stay stuck false
    // (still faded-out) the next time the window reappears from the tray.
    win.onFocusChanged(({ payload: focused }) => {
      if (focused) setVisible(true);
    }).then((fn) => {
      unlistenFocus = fn;
    }).catch((err) => console.error("onFocusChanged() failed:", err));

    return () => {
      unlistenClose?.();
      unlistenFocus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function requestClose() {
    if (closingRef.current) return;
    // "Minimize to tray" only hides the window (the tray icon's "Show
    // Captr" / left-click brings it back); a real close still fully quits,
    // matching this being purely a UX preference, not a background-service
    // mode.
    const closeToTray = useSettingsStore.getState().settings?.close_to_tray;
    closingRef.current = true;
    setVisible(false);
    setTimeout(() => {
      const win = getCurrentWindow();
      const action = closeToTray ? win.hide() : win.close();
      action.catch((err) => console.error("window hide/close failed:", err));
      closingRef.current = false;
    }, FADE_MS);
  }

  return (
    <WindowChromeContext.Provider value={{ requestClose }}>
      <div
        className={`h-screen w-screen overflow-hidden rounded-window bg-linear-to-b from-bg-top to-bg-bottom text-text transition-all ${
          visible ? "scale-100 opacity-100" : "scale-[0.98] opacity-0"
        }`}
        style={{ transitionDuration: `${FADE_MS}ms`, transitionTimingFunction: "var(--ease-smooth)" }}
      >
        <AnimatedBackground />
        {/* relative + z-10: stacks above AnimatedBackground's z-0 layer
         * regardless of DOM-order tie-breaking - see the z-index note in
         * MainView.tsx for why an explicit index matters here rather than
         * relying on paint order alone. */}
        <div className="relative z-10 flex h-full w-full flex-col">{children}</div>
      </div>
    </WindowChromeContext.Provider>
  );
}
