import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Frame } from "../lib/Frame";
import type { EffectProps } from "../lib/schema";
import { useEnvelope } from "../lib/timing";

/** P05 · Pro — words land one after another. `position: "upper"` for vertical clips. */
export const StaggeredKineticTitle: React.FC<EffectProps & { stagger?: number; position?: "center" | "upper" }> = (p) => {
  const { width, height, fps } = useVideoConfig();
  const size = Math.min(height * 0.075, width * 0.09);
  const frame = useCurrentFrame();
  const out = useEnvelope(p.enter, p.hold, p.exit);
  const words = p.text.split(/\s+/).filter(Boolean);
  const stagger = (p.stagger ?? 0.12) * fps;
  return (
    <Frame p={p}>
      <div
        style={{
          position: "absolute",
          left: "8%",
          right: "8%",
          top: p.position === "upper" ? "16%" : "50%",
          transform: p.position === "upper" ? undefined : "translateY(-50%)",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: `${height * 0.012}px ${height * 0.022}px`,
          opacity: 1 - out.outP,
        }}
      >
        {words.map((w, i) => {
          const s = spring({ frame: frame - i * stagger, fps, config: { damping: 14, stiffness: 160, mass: 0.6 } });
          const last = i === words.length - 1 && words.length > 1;
          return (
            <span
              key={i}
              style={{
                fontSize: size,
                fontWeight: 900,
                textTransform: "uppercase",
                color: last ? p.accent : p.textColor,
                WebkitTextStroke: `${Math.max(2, height * 0.004)}px rgba(0,0,0,.85)`,
                paintOrder: "stroke fill",
                display: "inline-block",
                opacity: Math.min(1, s * 1.4),
                transform: `translateY(${(1 - s) * height * 0.05}px) scale(${0.85 + 0.15 * s})`,
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </Frame>
  );
};
