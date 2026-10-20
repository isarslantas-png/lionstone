import React from "react";
import { useVideoConfig } from "remotion";
import { Frame } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** F05 · Free — name + title on a quiet translucent plate, inside action-safe. */
export const EditorialLowerThird: React.FC<EffectProps & { plateOpacity?: number }> = (p) => {
  const { width, height } = useVideoConfig();
  const bar = useEnvelope(p.enter * 0.7, p.hold + p.enter * 0.3, p.exit);
  const name = useEnvelope(p.enter, p.hold, p.exit, 0.08);
  const title = useEnvelope(p.enter, p.hold, p.exit, 0.18);
  const slide = (x: number) => `translateX(${(1 - x) * width * 0.02}px)`;
  return (
    <Frame p={p}>
      <div
        style={{
          position: "absolute",
          left: width * 0.07,
          bottom: height * 0.12,
          display: "flex",
          alignItems: "stretch",
          gap: width * 0.008,
        }}
      >
        <div
          style={{
            width: Math.max(4, width / 320),
            background: p.accent,
            transform: `scaleY(${bar.inP})`,
            transformOrigin: "bottom",
            opacity: 1 - bar.outP,
          }}
        />
        <div
          style={{
            background: `rgba(0,0,0,${p.plateOpacity ?? 0.55})`,
            padding: `${height * 0.014}px ${width * 0.012}px`,
            opacity: name.opacity,
            transform: slide(name.inP),
          }}
        >
          <div style={{ fontSize: height * 0.042, fontWeight: 700, lineHeight: 1.15 }}>{p.text}</div>
          {p.subtext ? (
            <div style={{ fontSize: height * 0.028, opacity: title.opacity * 0.9, marginTop: height * 0.006 }}>
              {p.subtext}
            </div>
          ) : null}
        </div>
      </div>
    </Frame>
  );
};
