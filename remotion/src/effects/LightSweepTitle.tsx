import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** P01 · Pro — a controlled sheen sweeps across the title. */
export const LightSweepTitle: React.FC<EffectProps & { sweepAngle?: number; intensity?: number }> = (p) => {
  const { height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const e = useEnvelope(p.enter, p.hold, p.exit);
  const t = frame / fps;
  const pos = interpolate(t, [p.enter * 0.5, p.enter * 0.5 + 1.1], [-30, 130], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const angle = p.sweepAngle ?? 20;
  const glow = p.intensity ?? 0.85;
  const common: React.CSSProperties = {
    fontSize: height * 0.08,
    fontWeight: 800,
    letterSpacing: "-0.01em",
    gridArea: "1 / 1",
  };
  return (
    <Frame p={p}>
      <div style={centered}>
        <div style={{ display: "grid", opacity: e.opacity, transform: `scale(${0.97 + 0.03 * e.inP})` }}>
          <div style={{ ...common, color: p.textColor }}>{p.text}</div>
          <div
            style={{
              ...common,
              color: "transparent",
              backgroundImage: `linear-gradient(${90 + angle}deg, transparent ${pos - 12}%, rgba(255,255,255,${glow}) ${pos}%, ${p.accent} ${pos + 3}%, transparent ${pos + 14}%)`,
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              filter: "drop-shadow(0 0 12px rgba(255,220,150,.35))",
            }}
          >
            {p.text}
          </div>
        </div>
        {p.subtext ? (
          <div style={{ fontSize: height * 0.03, marginTop: height * 0.016, opacity: e.opacity * 0.8 }}>{p.subtext}</div>
        ) : null}
      </div>
    </Frame>
  );
};
