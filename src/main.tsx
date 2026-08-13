import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import App from "./App";
import { CaptureOverlay } from "./components/overlay/CaptureOverlay";
import { RecordControlBar } from "./components/recordbar/RecordControlBar";
import "./styles/index.css";

// Every Tauri window in this app loads the same built SPA; which
// component actually renders is picked by the window's own label (set at
// creation time in lib/captureActions.ts etc.) rather than a router, since
// there are only a handful of distinct window "kinds" and each is a
// self-contained full-window UI, not a set of navigable pages.
function Root() {
  switch (getCurrentWindow().label) {
    case "capture-overlay":
      return <CaptureOverlay />;
    case "record-bar":
      return <RecordControlBar />;
    default:
      return <App />;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
