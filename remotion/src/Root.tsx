import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { CinematicFade } from "./effects/CinematicFade";
import { SlowRise } from "./effects/SlowRise";
import { LineReveal } from "./effects/LineReveal";
import { ChapterCard } from "./effects/ChapterCard";
import { EditorialLowerThird } from "./effects/EditorialLowerThird";
import { LetterSpacingReveal } from "./effects/LetterSpacingReveal";
import { defaults, effectSchema, EffectProps } from "./lib/schema";
import { totalSeconds } from "./lib/timing";

const FPS = 30;

/** Duration and size follow the props, so Lionstone can render any event length/aspect. */
const meta: CalculateMetadataFunction<EffectProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.round(totalSeconds(props) * FPS) + 6),
  width: props.width ?? 1920,
  height: props.height ?? 1080,
  fps: FPS,
});

// id must match "composition" in effects/catalog/*.json
const FREE_PACK: Array<{ id: string; component: React.FC<any>; props: Partial<EffectProps> }> = [
  { id: "CinematicFade", component: CinematicFade, props: { enter: 1.2, hold: 3, exit: 0.6 } },
  { id: "SlowRise", component: SlowRise, props: { enter: 0.85, hold: 3, exit: 0.5 } },
  { id: "LineReveal", component: LineReveal, props: { enter: 1, hold: 3, exit: 0.5 } },
  { id: "ChapterCard", component: ChapterCard, props: { enter: 0.6, hold: 2.4, exit: 0.5, number: 1, text: "Yapay Zekâ ile Kurgu", subtext: "Bölüm 1" } },
  { id: "EditorialLowerThird", component: EditorialLowerThird, props: { enter: 0.6, hold: 4, exit: 0.5, text: "İsmail Arslantaş", subtext: "Marka ve İçerik Tasarım Uzmanı" } },
  { id: "LetterSpacingReveal", component: LetterSpacingReveal, props: { enter: 1.3, hold: 2.5, exit: 0.6 } },
];

export const Root: React.FC = () => (
  <>
    {FREE_PACK.map(({ id, component, props }) => (
      <Composition
        key={id}
        id={id}
        component={component}
        schema={effectSchema}
        defaultProps={defaults(props)}
        calculateMetadata={meta}
        durationInFrames={150}
        fps={FPS}
        width={1920}
        height={1080}
      />
    ))}
  </>
);
