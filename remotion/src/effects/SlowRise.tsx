import React from "react";
import { useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F02 · Free — title rises gently from below and settles. */
export const SlowRise: React.FC<EffectProps> = (p) => {
  const { height } = useVideoConfig();
  const dist = height * 0.03;
  const a = useEnvelope(p.enter, p.hold, p.exit);
  const b = useEnvelope(p.enter, p.hold, p.exit, 0.15);
  return (
    <Frame p={p}>
      <div style={centered}>
        <div
          style={{
            fontSize: height * 0.07,
            fontWeight: 700,
            opacity: a.opacity,
            transform: `translateY(${(1 - a.inP) * dist}px)`,
          }}
        >
          {p.text}
        </div>
        {p.subtext ? (
          <div
            style={{
              fontSize: height * 0.032,
              marginTop: height * 0.012,
              opacity: b.opacity * 0.85,
              transform: `translateY(${(1 - b.inP) * dist}px)`,
            }}
          >
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
