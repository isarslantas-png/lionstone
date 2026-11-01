import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** P03 · Pro — layered title planes drift at different speeds (depth). */
export const DepthParallaxTitle: React.FC<EffectProps & { titleDrift?: number }> = (p) => {
  const { width, height, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const e = useEnvelope(p.enter, p.hold, p.exit);
  const prog = frame / durationInFrames - 0.5;
  const drift = (p.titleDrift ?? 0.025) * width;
  const layer = (depth: number, extra: React.CSSProperties) => (
    <div
      style={{
        ...centered,
        transform: `translateX(${-prog * drift * depth}px) scale(${1 + 0.04 * depth * (1 - e.inP)})`,
        ...extra,
      }}
    >
      <div style={{ fontSize: height * 0.075, fontWeight: 800 }}>{p.text}</div>
      {p.subtext ? <div style={{ fontSize: height * 0.03, marginTop: height * 0.015 }}>{p.subtext}</div> : null}
    </div>
  );
  return (
    <Frame p={p}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,.45))", opacity: e.opacity }} />
      {layer(2.2, { color: p.accent, opacity: e.opacity * 0.18, filter: "blur(6px)" })}
      {layer(1.4, { color: "#000", opacity: e.opacity * 0.35, filter: "blur(3px)" })}
      {layer(1, { color: p.textColor, opacity: e.opacity })}
    </Frame>
  );
};
