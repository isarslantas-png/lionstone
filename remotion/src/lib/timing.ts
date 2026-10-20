import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export type Envelope = {
  /** 0→1 entrance progress (eased) */
  inP: number;
  /** 0→1 exit progress (eased) */
  outP: number;
  /** overall opacity 0→1→0 */
  opacity: number;
  seconds: number;
};

/** Enter / hold / exit envelope in seconds, starting `delay` seconds in. */
export function useEnvelope(
  enter: number,
  hold: number,
  exit: number,
  delay = 0,
  ease: (t: number) => number = Easing.out(Easing.cubic),
): Envelope {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps - delay;
  const inP = interpolate(t, [0, Math.max(enter, 1e-3)], [0, 1], { ...clamp, easing: ease });
  const outStart = enter + hold;
  const outP = interpolate(t, [outStart, outStart + Math.max(exit, 1e-3)], [0, 1], {
    ...clamp,
    easing: Easing.in(Easing.quad),
  });
  return { inP, outP, opacity: inP * (1 - outP), seconds: t };
}

export const totalSeconds = (p: { enter: number; hold: number; exit: number }) =>
  p.enter + p.hold + p.exit;
