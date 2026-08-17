import type { ReactNode } from "react";

/** Flat elevated card - descendant of widgets/card.py's `Card`. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-card border border-border bg-surface p-4 shadow-sm shadow-black/5 ${className}`}>
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
