import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "../icons/Icon";

type Variant = "primary" | "glass" | "plain";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: Variant;
  pill?: boolean;
  selected?: boolean;
  icon?: IconName;
  iconSize?: number;
  /** Overrides the icon's color (a CSS color/token), e.g. always-red for
   * the record button regardless of theme/selection - mirrors buttons.py's
   * `icon_color_role`. */
  iconColorClassName?: string;
  width?: number;
  height?: number;
  children?: ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-linear-to-br from-accent to-accent-glow text-accent-text font-semibold shadow-[0_4px_16px_-2px_var(--accent-glow-shadow)] hover:shadow-[0_6px_20px_-2px_var(--accent-glow-shadow)] hover:brightness-110",
  glass: "bg-surface border border-border hover:bg-surface-strong hover:border-highlight-edge",
  plain: "hover:bg-hover active:bg-pressed",
};

/** Pill-leaning button (or a circular icon button via `pill`) with a spring
 * press animation - direct descendant of widgets/buttons.py's
 * `ModernButton`, redesigned away from flat Material-style buttons toward
 * glowing/glassy surfaces that visibly compress on click. */
export function Button({
  variant = "glass",
  pill = false,
  selected = false,
  icon,
  iconSize = 16,
  iconColorClassName,
  width,
  height = 32,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const radius = pill ? "9999px" : "var(--radius-control)";
  const selectedClasses =
    variant === "plain" && selected
      ? "bg-accent/15 text-accent shadow-[0_0_0_1px_var(--accent-glow-shadow)]"
      : "";

  return (
    <button
      type="button"
      style={{ width, height, borderRadius: radius, transitionTimingFunction: "var(--ease-spring)" }}
      className={`flex shrink-0 cursor-pointer items-center justify-center gap-1.5 text-sm text-text transition-all duration-200 active:scale-[0.94] disabled:cursor-default disabled:opacity-40 disabled:active:scale-100 ${variantClasses[variant]} ${selectedClasses} ${className}`}
      {...rest}
    >
      {icon && (
        <Icon
          name={icon}
          size={iconSize}
          className={iconColorClassName ?? (selected ? "text-accent" : variant === "primary" ? "text-accent-text" : "text-text")}
        />
      )}
      {children}
    </button>
  );
}
