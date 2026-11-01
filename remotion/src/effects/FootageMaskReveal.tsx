import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { EffectProps } from "../lib/schema";

/**
 * P02 · Pro — the footage underneath shows *through* the letters, then the
 * letters grow until the full scene is revealed. Rendered as a black matte with
 * a text-shaped hole, so it composites over any footage.
 */
export const FootageMaskReveal: React.FC<EffectProps & { openScale?: number }> = (p) => {
  const { width, height, fps } = useVideoConfig();
  const t = useCurrentFrame() / fps;
  const holdEnd = p.enter + p.hold;
  const scale = interpolate(t, [holdEnd, holdEnd + p.exit], [1, p.openScale ?? 14], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  const matte = interpolate(t, [0, p.enter * 0.6], [0, 1], { extrapolateRight: "clamp" });
  const fade = interpolate(t, [holdEnd + p.exit * 0.7, holdEnd + p.exit], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const size = height * 0.2;
  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
      <defs>
        <mask id="hole">
          <rect width={width} height={height} fill="white" />
          <text
            x={width / 2}
            y={height / 2}
            textAnchor="middle"
            dominantBaseline="central"
            fontFamily={p.fontFamily}
            fontWeight={900}
            fontSize={size}
            fill="black"
            transform={`translate(${width / 2} ${height / 2}) scale(${scale}) translate(${-width / 2} ${-height / 2})`}
          >
            {p.text.toUpperCase()}
          </text>
        </mask>
      </defs>
      <rect width={width} height={height} fill="#0B0B0D" mask="url(#hole)" opacity={matte * fade} />
    </svg>
  );
};
