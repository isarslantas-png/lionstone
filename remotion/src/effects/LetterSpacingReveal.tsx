import React from "react";
import { Easing, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F06 · Free — tracking eases from wide to normal. Not for small text. */
export const LetterSpacingReveal: React.FC<EffectProps & { trackingFrom?: number; trackingTo?: number }> = (p) => {
  const { height } = useVideoConfig();
  const e = useEnvelope(p.enter, p.hold, p.exit, 0, Easing.out(Easing.poly(4)));
  const from = p.trackingFrom ?? 0.45;
  const to = p.trackingTo ?? 0.04;
  const sub = useEnvelope(p.enter, p.hold, p.exit, p.enter * 0.6);
  return (
    <Frame p={p}>
      <div style={centered}>
        <div
          style={{
            fontSize: height * 0.08,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: `${from + (to - from) * e.inP}em`,
            opacity: e.opacity,
            filter: `blur(${(1 - e.inP) * 4}px)`,
          }}
        >
          {p.text}
        </div>
        {p.subtext ? (
          <div style={{ fontSize: height * 0.03, marginTop: height * 0.02, opacity: sub.opacity * 0.8 }}>
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
