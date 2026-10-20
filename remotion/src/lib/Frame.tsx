import React from "react";
import { AbsoluteFill } from "remotion";
import type { EffectProps } from "./schema";

/** Backdrop + title-safe area (90% / 80%). Effects render inside `children`. */
export const Frame: React.FC<{ p: EffectProps; children: React.ReactNode }> = ({ p, children }) => (
  <AbsoluteFill
    style={{
      background:
        p.backdrop === "preview"
          ? "linear-gradient(135deg, #2b3a4a 0%, #4a4040 55%, #6b4e3d 100%)"
          : "transparent",
      fontFamily: p.fontFamily,
      color: p.textColor,
    }}
  >
    {children}
  </AbsoluteFill>
);

export const centered: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  textAlign: "center",
  padding: "0 10%",
};
