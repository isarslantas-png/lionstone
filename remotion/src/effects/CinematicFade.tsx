import React from "react";
import { useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F01 · Free — soft opacity fade with optional background dim. */
export const CinematicFade: React.FC<EffectProps & { dim?: number }> = (p) => {
  const { height } = useVideoConfig();
  const e = useEnvelope(p.enter, p.hold, p.exit);
  const sub = useEnvelope(p.enter, p.hold, p.exit, 0.2);
  return (
    <Frame p={p}>
      <div style={{ position: "absolute", inset: 0, background: "#000", opacity: e.opacity * (p.dim ?? 0.35) }} />
      <div style={centered}>
        <div
          style={{
            fontSize: height * 0.075,
            fontWeight: 700,
            letterSpacing: "-0.01em",
            opacity: e.opacity,
            textShadow: "0 3px 18px rgba(0,0,0,.45)",
          }}
        >
          {p.text}
        </div>
        {p.subtext ? (
          <div style={{ fontSize: height * 0.032, marginTop: height * 0.015, opacity: sub.opacity * 0.85 }}>
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
