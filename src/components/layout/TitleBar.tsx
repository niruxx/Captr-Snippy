import { getCurrentWindow } from "@tauri-apps/api/window";
import { Icon, type IconName } from "../icons/Icon";
import { useWindowChrome } from "./WindowFrame";

const win = getCurrentWindow();

/**
 * Custom titlebar. `data-tauri-drag-region` (bare/"true") only starts a
 * drag when the *exact* mousedown target carries the attribute - Tauri's
 * injected listener walks the click's composed path upward and returns as
 * soon as it hits an element with the attribute, so a bare attribute on an
 * ancestor never fires for clicks that land on a plain child element (text,
 * icons, empty spacers) nested inside it, and - worse - short-circuits
 * before reaching any *further* ancestor's attribute at all. `"deep"` is
 * the variant that means "any descendant click counts", which is what a
 * whole-bar drag region actually needs; it's set once here, on the
 * outermost element, with no other nested `data-tauri-drag-region` in this
 * subtree. Buttons still work normally - Tauri's walk blocks dragging as
 * soon as it meets a clickable element (button/link/input/...) that has no
 * drag-region attribute of its own.
 */
export function TitleBar() {
  const { requestClose } = useWindowChrome();

  return (
    <div data-tauri-drag-region="deep" className="flex h-9 shrink-0 select-none items-center pl-4">
      <span className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-linear-to-br from-accent to-accent-glow shadow-[0_0_8px_var(--accent-glow-shadow)]" />
        <span className="text-[13px] font-semibold tracking-tight text-text-secondary">Snippy</span>
      </span>
      <div className="flex-1" />
      <div className="flex items-center gap-0.5 pr-2">
        <TitleBarButton icon="minimize" label="Minimize" onClick={() => win.minimize().catch(console.error)} />
        <TitleBarButton icon="maximize" label="Maximize" onClick={() => win.toggleMaximize().catch(console.error)} />
        <TitleBarButton icon="close" label="Close" danger onClick={requestClose} />
      </div>
    </div>
  );
}

function TitleBarButton({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: IconName;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`flex h-6 w-6 cursor-pointer items-center justify-center rounded-full text-text-tertiary transition-all duration-150 active:scale-90 ${
        danger ? "hover:bg-error hover:text-white" : "hover:bg-hover hover:text-text"
      }`}
    >
      <Icon name={icon} size={12} />
    </button>
  );
}
