import type { CSSProperties } from "react";
import { percent } from "../lib/format";

type ScoreRingProps = {
  score: number | null;
};

export function ScoreRing({ score }: ScoreRingProps) {
  return (
    <div
      className="score-ring"
      style={{ "--score": `${(score ?? 0) * 360}deg` } as CSSProperties}
    >
      <span>{percent(score)}</span>
    </div>
  );
}
