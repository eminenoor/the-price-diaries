import * as Plot from "@observablehq/plot";
import { useEffect, useRef } from "react";

import type { Anomaly, PricePoint } from "../api";
import { useMode } from "../mode";

interface PriceChartProps {
  history: PricePoint[];
  anomalies: Anomaly[];
  target: number | null;
}

const DAY = 24 * 60 * 60 * 1000;
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

/** The chart in one sentence, for screen readers. */
export function describe(history: PricePoint[], target: number | null): string {
  if (history.length === 0) return "Price chart, no checks yet.";
  const prices = history.map((p) => p.member_price ?? p.price);
  const fmt = (n: number) => `${n.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} lira`;
  const first = dayMonth.format(new Date(history[0].checked_at));
  const last = dayMonth.format(new Date(history[history.length - 1].checked_at));
  const alert = target ? ` Your alert price is ${fmt(target)}.` : "";
  return (
    `Price chart from ${first} to ${last}: lowest ${fmt(Math.min(...prices))}, ` +
    `highest ${fmt(Math.max(...prices))}, now ${fmt(prices[prices.length - 1])}.${alert}`
  );
}

/**
 * Price over time on a torn paper strip: a step line (prices jump between
 * checks), your alert price as a dashed line, unusual rises as red rings and
 * the lowest price as a gold dot. Dots for every check only when there are
 * under three days of data, so a short history is still visible.
 */
export function PriceChart({ history, anomalies, target }: PriceChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { mode } = useMode();

  useEffect(() => {
    const node = ref.current;
    if (!node || history.length === 0) return;

    // Plot writes colours as SVG attributes, where var() isn't reliable, so read the tokens.
    const token = (name: string) => getComputedStyle(node).getPropertyValue(name).trim();
    const ink = token("--chart-ink");
    const warn = token("--chart-warn");
    const gold = token("--gold");

    const data = history.map((p) => ({
      date: new Date(p.checked_at),
      price: p.member_price ?? p.price,
    }));
    const flagged = anomalies.map((a) => ({ date: new Date(a.checked_at), price: a.price }));
    const low = data.reduce((a, b) => (b.price <= a.price ? b : a));
    const span = data[data.length - 1].date.getTime() - data[0].date.getTime();
    const short = span < 3 * DAY;

    const chart = Plot.plot({
      width: node.clientWidth,
      height: 260,
      marginLeft: 64,
      marginBottom: 36,
      style: {
        background: "transparent",
        color: ink,
        fontFamily: "Figtree, sans-serif",
        fontSize: "13px",
        fontWeight: "500",
      },
      x: {
        type: "time",
        label: null,
        ticks: short ? 3 : 6,
        tickFormat: (d: Date) => dayMonth.format(d),
        ...(short ? { inset: 24 } : {}),
      },
      y: {
        label: "₺",
        grid: true,
        nice: true,
        tickFormat: (d: number) => d.toLocaleString("tr-TR"),
      },
      marks: [
        target
          ? Plot.ruleY([target], { stroke: ink, strokeWidth: 1.5, strokeDasharray: "6 5" })
          : null,
        Plot.lineY(data, {
          x: "date",
          y: "price",
          curve: "step-after",
          stroke: ink,
          strokeWidth: 2.5,
        }),
        short ? Plot.dot(data, { x: "date", y: "price", r: 3.5, fill: ink }) : null,
        Plot.dot(flagged, { x: "date", y: "price", r: 7, stroke: warn, strokeWidth: 2.5, fill: "none" }),
        Plot.dot([low], { x: "date", y: "price", r: 6.5, fill: gold, stroke: ink, strokeWidth: 1.5 }),
        Plot.tip(data, Plot.pointerX({ x: "date", y: "price" })),
      ],
    });
    // One labelled image for screen readers; the liner notes below have every check as text.
    chart.setAttribute("aria-hidden", "true");
    chart.querySelectorAll("[aria-label]").forEach((el) => el.removeAttribute("aria-label"));
    node.replaceChildren(chart);
    return () => chart.remove();
  }, [history, anomalies, target, mode]);

  return (
    <figure className="chart">
      <div ref={ref} className="chart__canvas" role="img" aria-label={describe(history, target)} />
      <figcaption className="chart__legend">
        <span className="legend legend--low">Gold dot: lowest price</span>
        {anomalies.length > 0 && <span className="legend legend--unusual">Red ring: unusual rise</span>}
        {target ? <span className="legend legend--target">Dashed line: your alert price</span> : null}
      </figcaption>
    </figure>
  );
}
