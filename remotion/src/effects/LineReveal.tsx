import React from "react";
import { Easing, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F03 · Free — a thin rule opens horizontally under the title. */
export const LineReveal: React.FC<EffectProps> = (p) => {
  const { width, height } = useVideoConfig();
  const line = useEnvelope(p.enter, p.hold, p.exit, 0, Easing.inOut(Easing.cubic));
  const title = useEnvelope(p.enter * 0.65, p.hold + p.enter * 0.35, p.exit, p.enter * 0.35);
  const sub = useEnvelope(p.enter * 0.5, p.hold + p.enter * 0.5, p.exit, p.enter * 0.6);
  return (
    <Frame p={p}>
      <div style={centered}>
        <div style={{ fontSize: height * 0.065, fontWeight: 700, opacity: title.opacity }}>{p.text}</div>
        <div
          style={{
            width: width * 0.28,
            height: Math.max(3, height * 0.004),
            background: p.accent,
            margin: `${height * 0.018}px 0`,
            transform: `scaleX(${line.inP})`,
            opacity: 1 - line.outP,
          }}
        />
        {p.subtext ? (
          <div style={{ fontSize: height * 0.03, opacity: sub.opacity * 0.85 }}>{p.subtext}</div>
        ) : null}
      </div>
    </Frame>
  );
};
