import { z } from "zod";
import { zColor } from "@remotion/zod-types";

/** Props shared by every Lionstone title effect. Mirrors effects/catalog/*.json. */
export const effectSchema = z.object({
  text: z.string(),
  subtext: z.string(),
  number: z.number().int().min(0).optional(),
  enter: z.number().min(0).max(5),
  hold: z.number().min(0).max(30),
  exit: z.number().min(0).max(5),
  accent: zColor(),
  textColor: zColor(),
  fontFamily: z.string(),
  /** "preview" paints a backdrop for the Studio/README; "transparent" for compositing. */
  backdrop: z.enum(["transparent", "preview"]),
  width: z.number().int().optional(),
  height: z.number().int().optional(),
});

export type EffectProps = z.infer<typeof effectSchema>;

export const defaults = (overrides: Partial<EffectProps>): EffectProps => ({
  text: "Lionstone",
  subtext: "AI editing agent",
  enter: 1,
  hold: 3,
  exit: 0.6,
  accent: "#E8B04B",
  textColor: "#FFFFFF",
  fontFamily: "Inter, 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif",
  backdrop: "preview",
  ...overrides,
});
