import React from "react";
import { useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F04 · Free — full-frame card with chapter number and title. */
export const ChapterCard: React.FC<EffectProps & { background?: string }> = (p) => {
  const { height } = useVideoConfig();
  const bg = useEnvelope(p.enter, p.hold, p.exit);
  const num = useEnvelope(p.enter, p.hold, p.exit, 0.1);
  const title = useEnvelope(p.enter, p.hold, p.exit, 0.2);
  const sub = useEnvelope(p.enter, p.hold, p.exit, 0.3);
  return (
    <Frame p={{ ...p, backdrop: "transparent" }}>
      <div style={{ position: "absolute", inset: 0, background: p.background ?? "#0E0E10", opacity: bg.opacity }} />
      <div style={centered}>
        {p.number !== undefined ? (
          <div
            style={{
              color: p.accent,
              fontSize: height * 0.04,
              fontWeight: 700,
              letterSpacing: "0.2em",
              opacity: num.opacity,
              marginBottom: height * 0.02,
            }}
          >
            {String(p.number).padStart(2, "0")}
          </div>
        ) : null}
        <div
          style={{
            fontSize: height * 0.08,
            fontWeight: 800,
            opacity: title.opacity,
            transform: `translateY(${(1 - title.inP) * height * 0.012}px)`,
          }}
        >
          {p.text}
        </div>
        {p.subtext ? (
          <div style={{ fontSize: height * 0.03, marginTop: height * 0.02, opacity: sub.opacity * 0.7 }}>
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
