// A tiny synthesized camera-shutter click (two quick filtered noise bursts)
// via the Web Audio API - no bundled asset needed. Gated by the
// `capture_sound` setting; failures (no audio device, autoplay policy,
// etc.) are swallowed since a missing click shouldn't interrupt capturing.

let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (ctx) return ctx;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  ctx = new Ctor();
  return ctx;
}

function click(context: AudioContext, when: number, freq: number, durationMs: number) {
  const osc = context.createOscillator();
  const gain = context.createGain();
  osc.type = "square";
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.15, when);
  gain.gain.exponentialRampToValueAtTime(0.001, when + durationMs / 1000);
  osc.connect(gain);
  gain.connect(context.destination);
  osc.start(when);
  osc.stop(when + durationMs / 1000);
}

export function playCaptureSound() {
  try {
    const context = getContext();
    if (!context) return;
    const now = context.currentTime;
    click(context, now, 1800, 30);
    click(context, now + 0.05, 1200, 60);
  } catch {
    // best-effort
  }
}
