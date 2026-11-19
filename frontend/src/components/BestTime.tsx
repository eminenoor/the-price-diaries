import type { CSSProperties } from "react";

import type { BestTime } from "../api";
import { useMode } from "../mode";
import { backtestLine, bestTimeNote, placement } from "../scene";

/**
 * "best time to buy": a handwritten note, taped up and tilted at night, on when this
 * product has been cheapest; under it, in one small line, how waiting would have done.
 */
export function BestTimeNote({ best, id }: { best: BestTime; id: number }) {
  const { mode } = useMode();
  const style = mode === "night" ? ({ "--tilt": `${placement(id).rotate / 2}deg` } as CSSProperties) : undefined;
  const line = backtestLine(best.backtest);

  return (
    <section className="best-time" aria-labelledby="best-time-title">
      <h2 id="best-time-title" className="best-time__title">
        best time to buy
      </h2>
      <div className="best-time__note paper paper--taped" style={style}>
        <p className="best-time__words">{bestTimeNote(best)}</p>
        {line && <p className="best-time__check">{line}</p>}
      </div>
    </section>
  );
}
