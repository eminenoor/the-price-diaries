import * as Plot from "@observablehq/plot";
import { useEffect, useRef } from "react";

import type { Anomaly, PricePoint } from "../api";

interface PriceChartProps {
  history: PricePoint[];
  anomalies: Anomaly[];
  target: number | null;
}

/** Price over time, drawn with Observable Plot. Colors come from CSS tokens. */
export function PriceChart({ history, anomalies, target }: PriceChartProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || history.length < 2) return;

    const data = history.map((p) => ({ date: new Date(p.checked_at), price: p.price }));
    const flagged = anomalies.map((a) => ({ date: new Date(a.checked_at), price: a.price }));
    const low = data.reduce((a, b) => (b.price <= a.price ? b : a));

    const chart = Plot.plot({
      width: node.clientWidth,
      height: 280,
      marginLeft: 56,
      style: { background: "transparent", fontFamily: "var(--font-text)", fontSize: "13px" },
      x: { type: "time", label: null },
      y: { label: "₺", grid: true, nice: true, tickFormat: (d: number) => d.toLocaleString("tr-TR") },
      marks: [
        target ? Plot.ruleY([target], { stroke: "var(--chlorophyll)", strokeDasharray: "2 4" }) : null,
        Plot.lineY(data, {
          x: "date",
          y: "price",
          curve: "step-after", // prices jump; they don't glide between checks
          stroke: "var(--ink)",
          strokeWidth: 1.5,
        }),
        Plot.dot(flagged, { x: "date", y: "price", r: 4, stroke: "var(--rouge)", fill: "var(--paper)" }),
        Plot.dot([low], { x: "date", y: "price", r: 4, fill: "var(--chlorophyll)" }),
        Plot.tip(data, Plot.pointerX({ x: "date", y: "price" })),
      ],
    });
    node.replaceChildren(chart);
    return () => chart.remove();
  }, [history, anomalies, target]);

  return (
    <figure className="chart">
      <div ref={ref} className="chart__canvas" />
      <figcaption className="chart__legend">
        <span className="legend legend--low">Lowest price</span>
        <span className="legend legend--unusual">Unusual rise</span>
        {target ? <span className="legend legend--target">Your target</span> : null}
      </figcaption>
    </figure>
  );
}
