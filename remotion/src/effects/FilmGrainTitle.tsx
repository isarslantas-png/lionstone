import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** P04 · Pro — soft film grain, vignette and warm light behind a readable title. */
export const FilmGrainTitle: React.FC<EffectProps & { grain?: number; vignette?: number }> = (p) => {
  const { width, height } = useVideoConfig();
  const frame = useCurrentFrame();
  const e = useEnvelope(p.enter, p.hold, p.exit);
  const t = useEnvelope(p.enter, p.hold, p.exit, 0.3);
  const grain = p.grain ?? 0.35;
  return (
    <Frame p={p}>
      <svg width={width} height={height} style={{ position: "absolute", inset: 0, opacity: e.opacity * grain, mixBlendMode: "overlay" }}>
        <filter id="g">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={frame % 97} />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#g)" />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center, rgba(255,190,120,.10) 0%, transparent 45%, rgba(0,0,0,${p.vignette ?? 0.4}) 100%)`,
          opacity: e.opacity,
        }}
      />
      <div style={centered}>
        <div style={{ fontSize: height * 0.07, fontWeight: 600, color: "#F4EDE2", letterSpacing: "0.02em", opacity: t.opacity, textShadow: "0 2px 14px rgba(0,0,0,.6)" }}>
          {p.text}
        </div>
        {p.subtext ? (
          <div style={{ fontSize: height * 0.028, color: "#D8CFC2", marginTop: height * 0.016, opacity: t.opacity * 0.85, fontStyle: "italic" }}>
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
