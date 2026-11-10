import * as Plot from "@observablehq/plot";
import { useEffect, useRef, useState } from "react";

import type { Anomaly, PricePoint, Summary } from "../api";
import { formatCheck, formatTime } from "../format";
import { useMode } from "../mode";
import { layoutNotes, pencilNotes, timeAxis, type PencilNote } from "../scene";

interface PriceChartProps {
  history: PricePoint[];
  anomalies: Anomaly[];
  summary: Summary;
  target: number | null;
}

const DAY = 24 * 60 * 60 * 1000;
/** Horizontal space one x-axis label needs, in px. */
const TICK_ROOM = 84;
const MARGIN_LEFT = 64;
const MARGIN_RIGHT = 16;
const MARGIN_TOP = 28;
const MARGIN_BOTTOM = 36;
const HEIGHT = 300;
/** The paper halo around note text, in px on each side. */
const HALO = 3;

/** Measures a note in the handwriting font, with room for its halo. */
function measurer(font: string, size: number): (text: string) => { w: number; h: number } {
  // OffscreenCanvas measures the real font; without it (tests), estimate from the length.
  const ctx = typeof OffscreenCanvas === "undefined" ? null : new OffscreenCanvas(1, 1).getContext("2d");
  return (text) => {
    if (ctx) ctx.font = font;
    const w = ctx ? ctx.measureText(text).width : text.length * size * 0.45;
    return { w: w + 2 * HALO, h: size + 2 * HALO };
  };
}
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

/** The chart in one sentence, for screen readers. */
export function describe(history: PricePoint[], target: number | null): string {
  if (history.length === 0) return "Price chart, no checks yet.";
  const points = history.map((p) => ({ at: p.checked_at, price: p.member_price ?? p.price }));
  const prices = points.map((p) => p.price);
  const fmt = (n: number) => `${n.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} lira`;
  const first = dayMonth.format(new Date(history[0].checked_at));
  const last = dayMonth.format(new Date(history[history.length - 1].checked_at));
  const low = points.reduce((a, b) => (b.price <= a.price ? b : a));
  const alert = target ? ` Your alert price is ${fmt(target)}.` : "";
  const when = first === last ? `on ${first}` : `from ${first} to ${last}`;
  return (
    `Price chart ${when}: lowest ${fmt(low.price)} on ${dayMonth.format(new Date(low.at))}, ` +
    `highest ${fmt(Math.max(...prices))}, now ${fmt(prices[prices.length - 1])}.${alert}`
  );
}

/**
 * Price over time on a torn paper strip: a step line (prices jump between
 * checks), your alert price as a dashed line, unusual rises as red rings and
 * the lowest price as a gold dot. Dots for every check only when there are
 * under three days of data, so a short history is still visible. The x-axis
 * has at most one tick per day (see timeAxis). Needs at least two checks.
 *
 * Instead of stat boxes, handwritten pencil notes are pinned on the chart: an
 * arrow to the lowest point, the highest and 30-day low when they're new
 * numbers, and the alert price written on its dashed line (see pencilNotes).
 */
export function PriceChart({ history, anomalies, summary, target }: PriceChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { mode } = useMode();
  // The notes, when they don't fit on the chart: then they go in a row under it.
  const [row, setRow] = useState<string[] | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || history.length === 0) return;

    // Plot writes colours as SVG attributes, where var() isn't reliable, so read the tokens.
    const token = (name: string) => getComputedStyle(node).getPropertyValue(name).trim();
    const ink = token("--chart-ink");
    const warn = token("--chart-warn");
    const gold = token("--gold");
    const paper = token("--chart-paper");
    const pencil = token("--pencil");
    const hand = token("--font-hand");
    let cancelled = false;

    // The notes are measured in the handwriting font, so wait until it has loaded.
    const fonts = typeof document.fonts === "undefined" ? null : document.fonts;
    if (fonts) fonts.load(`24px ${hand}`).then(draw, draw);
    else draw();
    return () => {
      cancelled = true;
      node.replaceChildren();
    };

    function draw() {
      if (cancelled || !node) return;
      const data = history.map((p) => ({
        date: new Date(p.checked_at),
        price: p.member_price ?? p.price,
      }));
      const flagged = anomalies.map((a) => ({ date: new Date(a.checked_at), price: a.price }));
      const low = data.reduce((a, b) => (b.price <= a.price ? b : a));
      const span = data[data.length - 1].date.getTime() - data[0].date.getTime();
      const short = span < 3 * DAY;
      const width = node.clientWidth;
      const axis = timeAxis(
        data.map((d) => d.date),
        (width - MARGIN_LEFT) / TICK_ROOM,
      );

      // Room above and below the line for the notes.
      const prices = [...data.map((d) => d.price), ...(target ? [target] : [])];
      const lo = Math.min(...prices);
      const hi = Math.max(...prices);
      const range = hi - lo || lo * 0.1 || 1;
      const yDomain: [number, number] = [lo - range * 0.45, hi + range * 0.3];
      const inset = short ? 24 : 14; // small padding at both ends of the x-axis

      // The same scales Plot uses (explicit domains, so they match exactly), to
      // place the notes in px and convert them back for Plot.
      const frame = {
        left: MARGIN_LEFT,
        right: width - MARGIN_RIGHT,
        top: MARGIN_TOP,
        bottom: HEIGHT - MARGIN_BOTTOM,
      };
      const [t0, t1] = axis.domain.map((d) => d.getTime());
      const [xa, xb] = [frame.left + inset, frame.right - inset];
      const toX = (d: Date) => (t1 === t0 ? (xa + xb) / 2 : xa + ((d.getTime() - t0) / (t1 - t0)) * (xb - xa));
      const toY = (p: number) =>
        frame.bottom - ((p - yDomain[0]) / (yDomain[1] - yDomain[0])) * (frame.bottom - frame.top);
      const fromX = (x: number) => new Date(t1 === t0 ? t0 : t0 + ((x - xa) / (xb - xa)) * (t1 - t0));
      const fromY = (y: number) =>
        yDomain[0] + ((frame.bottom - y) / (frame.bottom - frame.top)) * (yDomain[1] - yDomain[0]);

      const fontSize = width < 500 ? 20 : 24;
      const notes = pencilNotes(history, summary, target);
      const at = (n: PencilNote) => (n.date ? { x: toX(n.date), y: toY(n.price) } : null);
      const layout = layoutNotes({
        notes: notes.map((n) => ({ kind: n.kind, text: n.text, at: at(n) })),
        line: data.map((d) => ({ x: toX(d.date), y: toY(d.price) })),
        dots: [
          ...(short ? data.map((d) => ({ x: toX(d.date), y: toY(d.price), r: 3.5 })) : []),
          ...flagged.map((d) => ({ x: toX(d.date), y: toY(d.price), r: 8.5 })),
          { x: toX(low.date), y: toY(low.price), r: 7.5 },
        ],
        lowest: { x: toX(low.date), y: toY(low.price), r: 7.5 },
        alertY: target ? toY(target) : null,
        frame,
        measure: measurer(`${fontSize}px ${hand}`, fontSize),
      });
      setRow(layout.fits ? null : notes.map((n) => n.text));

      // Notes in ink, so they pass AA on the paper; the arrow is red pencil (a graphic).
      const handText = {
        fill: ink,
        fontFamily: hand,
        fontSize,
        stroke: paper,
        strokeWidth: 5, // a paper halo, so the note stays readable over grid lines
        paintOrder: "stroke",
      };
      const placed = layout.fits
        ? layout.notes.map((n) => ({
            text: n.text,
            // Text starts inside the box, past the halo.
            date: fromX(n.box.x + HALO),
            price: fromY(n.box.y + n.box.h / 2),
          }))
        : [];

      const chart = Plot.plot({
        width,
        height: HEIGHT,
        marginTop: MARGIN_TOP,
        marginLeft: MARGIN_LEFT,
        marginRight: MARGIN_RIGHT,
        marginBottom: MARGIN_BOTTOM,
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
          domain: axis.domain,
          ticks: axis.ticks,
          tickFormat: (d: Date) => (axis.kind === "time" ? formatTime(d) : dayMonth.format(d)),
          inset,
        },
        y: {
          label: "₺",
          grid: true,
          domain: yDomain,
          ticks: 4,
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

          // Pencil: an arrow from the edge of the "lowest" note to the gold dot.
          layout.fits
            ? Plot.arrow([layout.arrow], {
                x1: (a: typeof layout.arrow) => fromX(a.from.x),
                y1: (a: typeof layout.arrow) => fromY(a.from.y),
                x2: (a: typeof layout.arrow) => fromX(a.to.x),
                y2: (a: typeof layout.arrow) => fromY(a.to.y),
                bend: 0,
                insetStart: 2,
                insetEnd: 10, // stop at the dot's edge
                stroke: pencil,
                strokeWidth: 2.25,
                headLength: 10,
              })
            : null,
          Plot.text(placed, {
            x: "date",
            y: "price",
            text: "text",
            textAnchor: "start",
            lineAnchor: "middle",
            ...handText,
          }),

          Plot.tip(
            data,
            Plot.pointerX({
              x: "date",
              y: "price",
              title: (d: { date: Date; price: number }) => formatCheck(d.date, d.price),
              fill: paper,
              stroke: ink,
              textPadding: 8,
              fontSize: 14, // Plot's default is 10px; nothing goes under 13px
              fontWeight: 700,
            }),
          ),
        ],
      });
      // One labelled image for screen readers; the liner notes below have every check as text.
      chart.setAttribute("aria-hidden", "true");
      chart.querySelectorAll("[aria-label]").forEach((el) => el.removeAttribute("aria-label"));
      node.replaceChildren(chart);
    }
  }, [history, anomalies, summary, target, mode]);

  return (
    <figure className="chart">
      <div ref={ref} className="chart__canvas" role="img" aria-label={describe(history, target)} />
      {row && (
        <ul className="chart__notes">
          {row.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      <figcaption className="chart__legend">
        <span className="legend legend--low">Gold dot: lowest price</span>
        {anomalies.length > 0 && <span className="legend legend--unusual">Red ring: unusual rise</span>}
        {target ? <span className="legend legend--target">Dashed line: your alert price</span> : null}
      </figcaption>
    </figure>
  );
}
