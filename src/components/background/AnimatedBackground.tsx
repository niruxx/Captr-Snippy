import { useEffect, useRef } from "react";
import { useSettingsStore } from "../../state/settingsStore";
import { getTheme } from "../../lib/themes";

/** Renders the current theme's animated background layer, absolutely
 * positioned behind all real content (see WindowFrame.tsx) and completely
 * inert (`pointer-events-none`) so it never intercepts clicks/drags. */
export function AnimatedBackground() {
  const themeId = useSettingsStore((s) => s.settings?.theme);
  const theme = getTheme(themeId ?? "classic");

  if (theme.background === "none") return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
      {theme.background === "snowfall" ? <SnowfallLayer /> : <BlobLayer kind={theme.background} />}
    </div>
  );
}

const BLOB_PALETTES: Record<"aurora" | "sunset", [string, string, string]> = {
  aurora: ["#4ee6b8", "#7c8cff", "#5cd6e7"],
  sunset: ["#e78c5c", "#ff6c8c", "#ffb85c"],
};

function BlobLayer({ kind }: { kind: "aurora" | "sunset" }) {
  const [c1, c2, c3] = BLOB_PALETTES[kind];
  return (
    <>
      <div
        className="bg-blob bg-blob-a"
        style={{ top: "-10%", left: "-10%", width: "60%", height: "60%", background: c1, opacity: 0.35 }}
      />
      <div
        className="bg-blob bg-blob-b"
        style={{ top: "20%", right: "-15%", width: "55%", height: "55%", background: c2, opacity: 0.3 }}
      />
      <div
        className="bg-blob bg-blob-c"
        style={{ bottom: "-15%", left: "20%", width: "50%", height: "50%", background: c3, opacity: 0.28 }}
      />
    </>
  );
}

interface Flake {
  x: number;
  y: number;
  r: number;
  speed: number;
  drift: number;
  phase: number;
}

/** A lightweight canvas particle system - CSS alone can't do freely-falling,
 * independently-drifting particles at this count without either a huge
 * number of DOM nodes or fighting the animation model, so this is the one
 * background flavor that isn't pure CSS. Resizes with the window and
 * cleans its RAF loop up on unmount/theme change. */
function SnowfallLayer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let flakes: Flake[] = [];
    let raf = 0;
    let width = 0;
    let height = 0;

    function resize() {
      const parent = canvas!.parentElement;
      width = parent?.clientWidth ?? window.innerWidth;
      height = parent?.clientHeight ?? window.innerHeight;
      canvas!.width = width;
      canvas!.height = height;
      const count = Math.round((width * height) / 9000);
      flakes = Array.from({ length: count }, () => spawnFlake(width, height, true));
    }

    function spawnFlake(w: number, h: number, randomizeY: boolean): Flake {
      return {
        x: Math.random() * w,
        y: randomizeY ? Math.random() * h : -10,
        r: 1 + Math.random() * 2.5,
        speed: 0.4 + Math.random() * 1.1,
        drift: 0.3 + Math.random() * 0.7,
        phase: Math.random() * Math.PI * 2,
      };
    }

    function tick() {
      ctx!.clearRect(0, 0, width, height);
      ctx!.fillStyle = "rgba(255, 255, 255, 0.85)";
      for (const f of flakes) {
        f.y += f.speed;
        f.phase += 0.01;
        f.x += Math.sin(f.phase) * f.drift * 0.3;
        if (f.y > height + 10) Object.assign(f, spawnFlake(width, height, false));
        ctx!.beginPath();
        ctx!.globalAlpha = 0.4 + f.r / 4;
        ctx!.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
      raf = requestAnimationFrame(tick);
    }

    resize();
    tick();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <>
      {/* Deliberately near-opaque regardless of light/dark OS theme - a
       * wintry night sky is the point, and a 50%-strength overlay would
       * wash out to a muddy gray on a light background instead. */}
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg, #0a1930 0%, #142848 100%)", opacity: 0.92 }}
      />
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
    </>
  );
}
