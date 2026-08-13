/**
 * Hand-drawn vector icon set - a direct port of snippy/icons.py's QPainter
 * drawers onto a 0-100 SVG viewBox (each icon.py coordinate * 100), so the
 * app keeps its exact existing visual identity instead of swapping in a
 * generic icon library. Color comes from `currentColor` (drive it with a
 * Tailwind text-* class on the wrapper), matching icons.py's `color` param.
 */
import type { SVGProps } from "react";

export type IconName =
  | "pen"
  | "highlight"
  | "line"
  | "arrow"
  | "rect"
  | "ellipse"
  | "text"
  | "redact"
  | "picker"
  | "crop"
  | "undo"
  | "settings"
  | "more"
  | "minimize"
  | "maximize"
  | "close"
  | "back"
  | "plus"
  | "fullscreen"
  | "timer"
  | "record"
  | "pause"
  | "play"
  | "stop"
  | "copy";

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "viewBox"> {
  name: IconName;
  size?: number;
}

const strokeBase = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

function Drawer({ name }: { name: IconName }) {
  switch (name) {
    case "pen":
      return (
        <g>
          <line {...strokeBase} strokeWidth={9} x1={22} y1={82} x2={60} y2={32} />
          <polygon fill="currentColor" points="58,34 74,16 84,26 68,42" />
        </g>
      );
    case "highlight":
      return <polygon fill="currentColor" points="18,80 54,20 74,32 38,90" />;
    case "line":
      return <line {...strokeBase} strokeWidth={9} x1={18} y1={82} x2={82} y2={18} />;
    case "arrow":
      return (
        <g>
          <line {...strokeBase} strokeWidth={9} x1={18} y1={82} x2={78} y2={22} />
          <polygon fill="currentColor" points="78,22 78,46 54,22" />
        </g>
      );
    case "rect":
      return <rect {...strokeBase} strokeWidth={9} x={16} y={24} width={68} height={52} rx={8} />;
    case "ellipse":
      return <ellipse {...strokeBase} strokeWidth={9} cx={50} cy={50} rx={36} ry={30} />;
    case "text":
      return <line {...strokeBase} strokeWidth={13} x1={28} y1={26} x2={72} y2={26} />;
    case "redact":
      return <rect fill="currentColor" x={14} y={26} width={72} height={48} rx={6} />;
    case "picker":
      return (
        <g>
          <line {...strokeBase} strokeWidth={11} x1={28} y1={84} x2={58} y2={54} />
          <circle fill="currentColor" cx={68} cy={34} r={16} />
        </g>
      );
    case "crop":
      return (
        <g {...strokeBase} strokeWidth={10}>
          <line x1={22} y1={14} x2={22} y2={44} />
          <line x1={22} y1={14} x2={52} y2={14} />
          <line x1={78} y1={86} x2={78} y2={56} />
          <line x1={78} y1={86} x2={48} y2={86} />
        </g>
      );
    case "undo":
      return (
        <g>
          <path {...strokeBase} strokeWidth={10} d="M32,36 C86,18 88,78 44,80" />
          <polygon fill="currentColor" points="32,36 48,28 42,48" />
        </g>
      );
    case "settings":
      return <GearIcon />;
    case "more":
      return (
        <g fill="currentColor">
          <circle cx={28} cy={50} r={6.5} />
          <circle cx={50} cy={50} r={6.5} />
          <circle cx={72} cy={50} r={6.5} />
        </g>
      );
    case "minimize":
      return <line {...strokeBase} strokeWidth={10} x1={24} y1={50} x2={76} y2={50} />;
    case "maximize":
      return <rect {...strokeBase} strokeWidth={9} x={26} y={26} width={48} height={48} rx={5} />;
    case "close":
      return (
        <g {...strokeBase} strokeWidth={10}>
          <line x1={27} y1={27} x2={73} y2={73} />
          <line x1={73} y1={27} x2={27} y2={73} />
        </g>
      );
    case "back":
      return <polyline {...strokeBase} strokeWidth={11} points="66,22 34,50 66,78" />;
    case "plus":
      return (
        <g {...strokeBase} strokeWidth={13}>
          <line x1={50} y1={24} x2={50} y2={76} />
          <line x1={24} y1={50} x2={76} y2={50} />
        </g>
      );
    case "fullscreen":
      return (
        <g {...strokeBase} strokeWidth={10}>
          <path d="M24,24 h16 M24,24 v16" />
          <path d="M76,24 h-16 M76,24 v16" />
          <path d="M24,76 h16 M24,76 v-16" />
          <path d="M76,76 h-16 M76,76 v-16" />
        </g>
      );
    case "timer":
      return (
        <g>
          <circle {...strokeBase} strokeWidth={9} cx={50} cy={56} r={32} />
          <line {...strokeBase} strokeWidth={9} x1={50} y1={56} x2={50} y2={36} />
          <line {...strokeBase} strokeWidth={9} x1={50} y1={56} x2={64} y2={56} />
          <line {...strokeBase} strokeWidth={9} x1={40} y1={14} x2={60} y2={14} />
          <line {...strokeBase} strokeWidth={9} x1={50} y1={14} x2={50} y2={24} />
        </g>
      );
    case "record":
      return <circle fill="currentColor" cx={50} cy={50} r={22} />;
    case "pause":
      return (
        <g fill="currentColor">
          <rect x={26} y={22} width={14} height={56} rx={3} />
          <rect x={60} y={22} width={14} height={56} rx={3} />
        </g>
      );
    case "play":
      return <polygon fill="currentColor" points="32,22 32,78 80,50" />;
    case "stop":
      return <rect fill="currentColor" x={28} y={28} width={44} height={44} rx={8} />;
    case "copy":
      return (
        <g {...strokeBase} strokeWidth={8}>
          <rect x={20} y={20} width={48} height={48} rx={6} />
          <rect x={34} y={34} width={48} height={48} rx={6} />
        </g>
      );
    default:
      return null;
  }
}

let gearMaskId = 0;

function GearIcon() {
  const id = `gear-hole-${gearMaskId++}`;
  const teeth = [0, 45, 90, 135, 180, 225, 270, 315];
  return (
    <g>
      <mask id={id}>
        <g fill="white">
          <circle cx={50} cy={50} r={24} />
          {teeth.map((deg) => (
            <rect key={deg} x={44} y={13} width={12} height={13} rx={3.6}
                  transform={`rotate(${deg} 50 50)`} />
          ))}
        </g>
        <circle cx={50} cy={50} r={11} fill="black" />
      </mask>
      <rect x={0} y={0} width={100} height={100} fill="currentColor" mask={`url(#${id})`} />
    </g>
  );
}

export function Icon({ name, size = 20, className, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      {...rest}
    >
      <Drawer name={name} />
    </svg>
  );
}
