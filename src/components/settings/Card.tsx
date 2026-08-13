import type { ReactNode } from "react";

/** Frosted glass panel - descendant of widgets/card.py's `Card`, given a
 * backdrop blur over the window's gradient so it reads as a distinct pane
 * of glass rather than a flat Material surface. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-card border border-highlight-edge bg-surface p-4 shadow-lg shadow-black/10 backdrop-blur-xl ${className}`}
    >
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold tracking-[0.12em] text-text-tertiary uppercase">
      <span className="h-1 w-1 rounded-full bg-accent" />
      {children}
    </div>
  );
}
