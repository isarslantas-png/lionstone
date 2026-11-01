import React from "react";
import { Img, useVideoConfig } from "remotion";
import { Frame, centered } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** P06 · Pro — logo, brand name and fine lines as a signature open / close. */
export const SignatureBrandReveal: React.FC<EffectProps & { logo?: string }> = (p) => {
  const { width, height } = useVideoConfig();
  const bg = useEnvelope(p.enter * 0.5, p.hold + p.enter * 0.5, p.exit);
  const l1 = useEnvelope(p.enter, p.hold, p.exit, 0.2);
  const l2 = useEnvelope(p.enter, p.hold, p.exit, 0.35);
  const name = useEnvelope(p.enter * 0.8, p.hold, p.exit, 0.35);
  const sub = useEnvelope(p.enter, p.hold, p.exit, 0.6);
  const line = (e: typeof l1) => (
    <div style={{ width: width * 0.22, height: Math.max(2, height / 540), background: p.accent, transform: `scaleX(${e.inP})`, opacity: 1 - e.outP }} />
  );
  return (
    <Frame p={{ ...p, backdrop: "transparent" }}>
      <div style={{ position: "absolute", inset: 0, background: "#0B0B0D", opacity: bg.opacity }} />
      <div style={centered}>
        {p.logo ? (
          <Img src={p.logo} style={{ height: height * 0.14, marginBottom: height * 0.03, opacity: name.opacity }} />
        ) : null}
        {line(l1)}
        <div
          style={{
            fontSize: height * 0.06,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: `${0.3 - 0.12 * name.inP}em`,
            margin: `${height * 0.03}px 0`,
            opacity: name.opacity,
          }}
        >
          {p.text}
        </div>
        {line(l2)}
        {p.subtext ? (
          <div style={{ fontSize: height * 0.024, marginTop: height * 0.03, opacity: sub.opacity * 0.7, letterSpacing: "0.12em" }}>
            {p.subtext}
          </div>
        ) : null}
      </div>
    </Frame>
  );
};
