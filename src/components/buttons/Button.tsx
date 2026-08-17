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
    "bg-accent text-accent-text font-medium shadow-[0_1px_3px_0_var(--accent-glow-shadow)] hover:bg-accent-hover hover:shadow-[0_2px_6px_0_var(--accent-glow-shadow)]",
  glass: "bg-surface border border-border hover:bg-hover",
  plain: "hover:bg-hover active:bg-pressed",
};

/** Pill-leaning button (or a circular icon button via `pill`) - flat fill/
 * outline surfaces with a Material-style neutral elevation shadow, a light
 * hover state layer, and a brief scale-down on press (no glow, no spring
 * overshoot). */
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
  const selectedClasses = variant === "plain" && selected ? "bg-accent/12 text-accent" : "";

  return (
    <button
      type="button"
      style={{ width, height, borderRadius: radius, transitionTimingFunction: "var(--ease-smooth)" }}
      className={`flex shrink-0 cursor-pointer items-center justify-center gap-1.5 text-sm text-text transition-all duration-150 active:scale-[0.97] disabled:cursor-default disabled:opacity-40 disabled:active:scale-100 ${variantClasses[variant]} ${selectedClasses} ${className}`}
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
