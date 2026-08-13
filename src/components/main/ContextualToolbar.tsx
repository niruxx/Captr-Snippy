import { Button } from "../buttons/Button";
import { ColorSwatch, WidthSwatch } from "./ColorSwatch";
import { useCaptureStore } from "../../state/captureStore";
import { ANNOT_COLORS, ANNOT_WIDTHS } from "../../lib/constants";
import type { ToolName } from "../../lib/annotation";
import type { IconName } from "../icons/Icon";

// tool name doubles as its Icon.tsx drawer name
const TOOLS: { name: ToolName; icon: IconName; tip: string }[] = [
  { name: "pen", icon: "pen", tip: "Pen" },
  { name: "highlight", icon: "highlight", tip: "Highlighter" },
  { name: "line", icon: "line", tip: "Line" },
  { name: "arrow", icon: "arrow", tip: "Arrow" },
  { name: "rect", icon: "rect", tip: "Rectangle" },
  { name: "ellipse", icon: "ellipse", tip: "Ellipse" },
  { name: "text", icon: "text", tip: "Text" },
  { name: "redact", icon: "redact", tip: "Redact / pixelate" },
  { name: "picker", icon: "picker", tip: "Color picker" },
  { name: "crop", icon: "crop", tip: "Crop" },
];

function Divider() {
  return <div className="mx-1 h-6 w-px shrink-0 bg-border-soft" />;
}

/** Floating pill toolbar over the preview - only shown once there's a
 * capture to annotate. Direct port of widgets/float_toolbar.py. */
export function ContextualToolbar() {
  const tool = useCaptureStore((s) => s.tool);
  const color = useCaptureStore((s) => s.color);
  const width = useCaptureStore((s) => s.width);
  const setTool = useCaptureStore((s) => s.setTool);
  const setColor = useCaptureStore((s) => s.setColor);
  const setWidth = useCaptureStore((s) => s.setWidth);
  const undo = useCaptureStore((s) => s.undo);

  return (
    <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 animate-pop-in items-center gap-0.5 rounded-full border border-highlight-edge bg-surface-strong/95 px-2.5 py-1.5 shadow-lg shadow-black/20 backdrop-blur-xl">
      {TOOLS.map(({ name, icon, tip }) => (
        <Button
          key={name}
          variant="plain"
          pill
          selected={tool === name}
          icon={icon}
          iconSize={17}
          width={32}
          height={32}
          aria-label={tip}
          title={tip}
          onClick={() => setTool(name)}
        />
      ))}

      <Divider />
      {ANNOT_COLORS.map((c) => (
        <ColorSwatch key={c} color={c} selected={color === c} onClick={() => setColor(c)} />
      ))}

      <Divider />
      {ANNOT_WIDTHS.map((w) => (
        <WidthSwatch key={w} widthValue={w} selected={width === w} onClick={() => setWidth(w)} />
      ))}

      <Divider />
      <Button
        variant="plain"
        pill
        icon="undo"
        iconSize={17}
        width={32}
        height={32}
        aria-label="Undo"
        title="Undo (Ctrl+Z)"
        onClick={() => undo()}
      />
    </div>
  );
}
