/// <reference types="node" />
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { Category, Product, Summary } from "./api";
import {
  contrast,
  floorsOf,
  inkOn,
  lighting,
  newsLine,
  shortName,
  SUBTITLE_MAX,
  pencilNotes,
  placement,
  statsOf,
  timeAxis,
  boxesOverlap,
  layoutNotes,
  segmentHitsBox,
  stepSegments,
  type NoteLayout,
  type NoteScene,
  type NoteToPlace,
  type Point,
  windowState,
  type WindowKind,
} from "./scene";

const summary = (overrides: Partial<Summary> = {}): Summary => ({
  current: 300,
  previous: 300,
  lowest: 250,
  lowest_at: "2026-10-01T09:00:00",
  highest: 360,
  highest_at: "2026-10-10T09:00:00",
  lowest_30d: 280,
  change_pct: 0,
  is_all_time_low: false,
  fake_sale: false,
  ...overrides,
});

const product = (overrides: Partial<Product> = {}): Product => ({
  id: 1,
  url: "https://www.gratis.com/x",
  name: "Toner",
  store: "gratis",
  category_id: null,
  target_price: null,
  image_url: null,
  last_error: null,
  blocked: false,
  created_at: "2026-09-01T09:00:00",
  summary: summary(),
  regular_price: null,
  size: null,
  unit_price: null,
  gtin: null,
  cheaper_elsewhere: null,
  sparkline: [],
  brand: null,
  ...overrides,
});

const storeName = (key: string) => key.charAt(0).toUpperCase() + key.slice(1);

describe("windowState", () => {
  const cases: [string, Partial<Product>, WindowKind, string][] = [
    ["blocked store", { blocked: true, last_error: "x" }, "blocked", "Gratis doesn't allow automated checks"],
    ["failed check", { last_error: "Store answered 503." }, "error", "last check failed"],
    ["never checked", { summary: null }, "waiting", "not checked yet"],
    ["fake sale", { summary: summary({ fake_sale: true, change_pct: -20, is_all_time_low: true }) }, "fake", "fake sale"],
    ["all-time low", { summary: summary({ change_pct: -7, is_all_time_low: true }) }, "deal", "lowest ever"],
    ["under alert", { target_price: 310 }, "deal", "below your alert price"],
    ["30-day low", { summary: summary({ current: 270, change_pct: -10 }) }, "deal", "lowest in 30 days"],
    ["small drop", { summary: summary({ change_pct: -3.04 }) }, "deal", "down 3.0%"],
    ["price up", { summary: summary({ change_pct: 6 }) }, "up", "up 6.0%"],
    ["no change", {}, "steady", "no change"],
    ["still at its all-time low", { summary: summary({ current: 250, lowest: 250, change_pct: 0, is_all_time_low: true }) }, "deal", "lowest ever"],
    ["still below the alert price", { target_price: 320, summary: summary({ change_pct: 0 }) }, "deal", "below your alert price"],
    ["never moved", { summary: summary({ current: 300, lowest: 300, highest: 300, change_pct: 0, is_all_time_low: true }) }, "steady", "no change"],
    ["up, but below the alert price", { target_price: 320, summary: summary({ change_pct: 4 }) }, "deal", "below your alert price"],
    ["one check", { summary: summary({ previous: null, change_pct: null, current: 250, lowest_30d: 250, is_all_time_low: true }) }, "first", "first check"],
    ["one check under alert", { target_price: 260, summary: summary({ previous: null, change_pct: null, current: 250 }) }, "deal", "below your alert price"],
  ];
  it.each(cases)("%s", (_, overrides, kind, words) => {
    expect(windowState(product(overrides), "Gratis")).toEqual({ kind, words });
  });
});

describe("lighting", () => {
  it.each([
    ["deal", "lamp", "open", false],
    ["fake", "rose", "half", false],
    ["steady", "dark", "closed", false],
    ["first", "dark", "closed", false],
    ["up", "dark", "closed", false],
    ["waiting", "dark", "closed", false],
    ["error", "dark", "closed", false],
    ["blocked", "dark", "closed", true],
  ] as const)("%s: %s light, %s curtains", (kind, light, curtains, blinds) => {
    expect(lighting(kind)).toEqual({ light, curtains, blinds });
  });
});

describe("shortName", () => {
  it.each([
    ["AHA BHA PHA Toner 150 ml", null, "AHA BHA PHA Toner"],
    ["Some By Mi AHA BHA PHA Toner 150 ml", "Some By Mi", "AHA BHA PHA Toner"],
    ["Vitamin D3 1000 IU, 90 tablets", null, "Vitamin D3 1000 IU"],
    ["Cold-Pressed Olive Oil 1 l", null, "Cold-Pressed Olive Oil"],
    ["Dishwasher Tablets 60 pcs", null, "Dishwasher Tablets"],
    ["Niacinamide 10% Toner 200 ml", null, "Niacinamide 10% Toner"],
    ["Some By Mi", "Some By Mi", "Some By Mi"],
  ])("%s", (name, brand, short) => {
    expect(shortName(name, brand)).toBe(short);
  });
});

describe("newsLine", () => {
  const deal = product({ id: 1, name: "Toner", summary: summary({ change_pct: -7, is_all_time_low: true }) });
  const fake = product({ id: 2, name: "Sunscreen", store: "watsons", summary: summary({ fake_sale: true }) });
  const fake2 = product({ id: 3, name: "Laundry liquid", summary: summary({ fake_sale: true }) });
  const steady = product({ id: 4, name: "Coffee" });

  it("leads with the best deal and warns about fake sales in one sentence", () => {
    expect(newsLine([steady, fake, deal], storeName)).toBe(
      "Toner is at its lowest ever at Gratis, but one sale is fake.",
    );
    expect(newsLine([deal, fake, fake2], storeName)).toMatch(/but 2 sales are fake\.$/);
  });

  it("names a single fake sale", () => {
    expect(newsLine([fake, steady], storeName)).toBe(
      "The sale on Sunscreen at Watsons is fake: it went up first.",
    );
  });

  it("keeps every line to about 60 characters, using the short name", () => {
    const long = (id: number, name: string, overrides: Partial<Product> = {}) =>
      product({ id, name, brand: "Some By Mi", ...overrides });
    const lines = [
      newsLine([long(1, "Some By Mi AHA BHA PHA 30 Days Miracle Toner 150 ml", deal), fake], storeName),
      newsLine([long(1, "AHA BHA PHA 30 Days Miracle Toner Extra Gentle Formula 150 ml", deal), fake, fake2], storeName),
      newsLine([long(2, "Red Tea Tightening Pore Clay Mask, 2 x 100 ml", fake)], storeName),
      newsLine([fake, fake2], storeName),
      newsLine([steady], storeName),
      newsLine([], storeName),
    ];
    for (const line of lines) expect(line.length, line).toBeLessThanOrEqual(SUBTITLE_MAX);
    expect(lines[0]).not.toMatch(/150 ml|Some By Mi/);
  });

  it("has something to say on quiet nights and empty buildings", () => {
    expect(newsLine([steady], storeName)).toBe("A quiet night. Nothing on your list got cheaper.");
    expect(newsLine([], storeName)).toMatch(/^No lights on yet/);
  });
});

describe("placement", () => {
  it("is stable for an id and differs between ids", () => {
    expect(placement(7)).toEqual(placement(7));
    expect(placement(7)).not.toEqual(placement(8));
  });

  it("never tilts more than 3 degrees and stays in range", () => {
    for (let id = 1; id <= 500; id++) {
      const p = placement(id);
      expect(Math.abs(p.rotate)).toBeLessThanOrEqual(3);
      expect(p.size).toBeGreaterThanOrEqual(0.62);
      expect(p.size).toBeLessThanOrEqual(1);
      expect(Math.abs(p.nudge)).toBeLessThanOrEqual(1);
      expect(p.drop).toBeGreaterThanOrEqual(0);
      expect(p.drop).toBeLessThanOrEqual(120);
    }
  });
});

describe("statsOf", () => {
  it("shows nothing that repeats the current price", () => {
    const one = summary({ current: 250, previous: null, lowest: 250, highest: 250, lowest_30d: 250 });
    expect(statsOf(one)).toEqual([]);
  });

  it("drops a stat that repeats another one", () => {
    const labels = statsOf(summary({ current: 300, lowest: 250, highest: 360, lowest_30d: 250 })).map((s) => s.label);
    expect(labels).toEqual(["Lowest", "Highest"]);
    expect(statsOf(summary()).map((s) => s.label)).toEqual(["Lowest", "Highest", "Lowest in 30 days"]);
  });
});

describe("pencilNotes", () => {
  const check = (day: number, price: number) => ({
    checked_at: new Date(2026, 10, day, 9, 17).toISOString(),
    price,
    member_price: null,
  });

  it("points at the lowest check and writes the alert price on its line", () => {
    const history = [check(1, 300), check(2, 360), check(3, 268.22), check(4, 300)];
    const s = summary({ current: 300, lowest: 268.22, highest: 360, lowest_30d: 268.22 });
    const notes = pencilNotes(history, s, 250);
    expect(notes.map((n) => [n.kind, n.text])).toEqual([
      ["lowest", "lowest ₺268,22 · 3 Nov"],
      ["highest", "highest ₺360,00"],
      ["alert", "alert ₺250,00"],
    ]);
    expect(notes[0].date).toEqual(new Date(2026, 10, 3, 9, 17));
  });

  it("adds the 30-day low only when it is a different number", () => {
    const history = [check(1, 200), check(2, 300), check(3, 280), check(4, 300)];
    const s = summary({ current: 300, lowest: 200, highest: 300, lowest_30d: 280 });
    expect(pencilNotes(history, s, null).map((n) => n.kind)).toEqual(["lowest", "low30"]);
  });
});

describe("layoutNotes", () => {
  const measure = (text: string) => ({ w: text.length * 10, h: 24 });
  const frame = { left: 64, right: 1100, top: 28, bottom: 264 };

  /** A step line through these (x, y) points, a gold dot on the lowest, and notes. */
  const scene = (
    line: Point[],
    { alertY = null, width = frame.right }: { alertY?: number | null; width?: number } = {},
  ): NoteScene => {
    const low = line.reduce((a, b) => (b.y >= a.y ? b : a)); // lowest price = largest y
    const high = line.reduce((a, b) => (b.y <= a.y ? b : a));
    const notes: NoteToPlace[] = [
      { kind: "lowest", text: "lowest ₺268,22 · 11 Nov", at: low },
      { kind: "highest", text: "highest ₺320,00", at: high },
    ];
    if (alertY !== null) notes.push({ kind: "alert", text: "alert ₺250,00", at: null });
    return {
      notes,
      line,
      dots: [...line.map((p) => ({ ...p, r: 3.5 })), { ...low, r: 7.5 }],
      lowest: { ...low, r: 7.5 },
      alertY,
      frame: { ...frame, right: width },
      measure,
    };
  };

  /** Checks a layout against everything it must keep clear of, independently. */
  function expectClear(s: NoteScene, layout: Extract<NoteLayout, { fits: true }>) {
    const segments = stepSegments(s.line);
    layout.notes.forEach((n, i) => {
      const b = n.box;
      expect(b.x >= s.frame.left && b.x + b.w <= s.frame.right, n.kind).toBe(true);
      expect(b.y >= s.frame.top && b.y + b.h <= s.frame.bottom, n.kind).toBe(true);
      for (const [p, q] of segments) expect(segmentHitsBox(p, q, b), `${n.kind} on the line`).toBe(false);
      for (const d of s.dots) {
        const dotBox = { x: d.x - d.r, y: d.y - d.r, w: 2 * d.r, h: 2 * d.r };
        expect(boxesOverlap(b, dotBox), `${n.kind} on a dot`).toBe(false);
      }
      layout.notes.slice(i + 1).forEach((m) => expect(boxesOverlap(b, m.box), `${n.kind}/${m.kind}`).toBe(false));
      if (n.kind !== "lowest") expect(segmentHitsBox(layout.arrow.from, layout.arrow.to, b)).toBe(false);
    });
  }

  it("puts every note next to its point, clear of the line, the dots and each other", () => {
    const s = scene([
      { x: 78, y: 120 },
      { x: 400, y: 80 },
      { x: 700, y: 150 },
      { x: 1086, y: 200 },
    ]);
    const layout = layoutNotes(s);
    expect(layout.fits).toBe(true);
    if (!layout.fits) return;
    expectClear(s, layout);
  });

  it("puts the lowest note near the gold dot, with the arrow from the note to the dot", () => {
    const s = scene([
      { x: 78, y: 100 },
      { x: 500, y: 180 },
      { x: 800, y: 120 },
      { x: 1086, y: 120 },
    ]);
    const layout = layoutNotes(s);
    if (!layout.fits) throw new Error("should fit");
    const note = layout.notes.find((n) => n.kind === "lowest")!.box;
    expect(layout.arrow.to).toEqual({ x: 500, y: 180 });
    // The arrow starts on the note's edge…
    const onEdge =
      (layout.arrow.from.x === note.x || layout.arrow.from.x === note.x + note.w ||
        layout.arrow.from.y === note.y || layout.arrow.from.y === note.y + note.h) &&
      layout.arrow.from.x >= note.x && layout.arrow.from.x <= note.x + note.w &&
      layout.arrow.from.y >= note.y && layout.arrow.from.y <= note.y + note.h;
    expect(onEdge).toBe(true);
    // …is long enough to read as an arrow, and short: the note is near the dot.
    const length = Math.hypot(layout.arrow.to.x - layout.arrow.from.x, layout.arrow.to.y - layout.arrow.from.y);
    expect(length).toBeGreaterThanOrEqual(34);
    expect(length).toBeLessThanOrEqual(90);
  });

  it("writes the alert price on its dashed line, clear of everything else", () => {
    const s = scene(
      [
        { x: 78, y: 100 },
        { x: 600, y: 160 },
        { x: 1086, y: 100 },
      ],
      { alertY: 220 },
    );
    const layout = layoutNotes(s);
    if (!layout.fits) throw new Error("should fit");
    const alert = layout.notes.find((n) => n.kind === "alert")!.box;
    expect(alert.y + alert.h === 217 || alert.y === 223).toBe(true); // just above or below the line
    expectClear(s, layout);
  });

  it("works for two days of data", () => {
    const s = scene([
      { x: 78, y: 90 },
      { x: 1086, y: 200 },
    ]);
    const layout = layoutNotes(s);
    if (!layout.fits) throw new Error("should fit");
    expectClear(s, layout);
  });

  it("gives up when the notes can't fit, so they go in a row under the chart", () => {
    const s = scene(
      [
        { x: 70, y: 40 },
        { x: 100, y: 250 },
        { x: 130, y: 40 },
        { x: 160, y: 250 },
      ],
      { width: 180, alertY: 150 },
    );
    expect(layoutNotes(s)).toEqual({ fits: false });
  });
});

describe("timeAxis", () => {
  const at = (day: number, hour = 9, minute = 17) => new Date(2026, 10, day, hour, minute);
  const label = (d: Date) => `${d.getDate()}/${d.getHours()}:${d.getMinutes()}`;

  it("runs from the first check to the last, one tick per day", () => {
    const axis = timeAxis([at(8), at(8, 21), at(9), at(10), at(10, 22)], 10);
    expect(axis.kind).toBe("day");
    expect(axis.domain).toEqual([at(8), at(10, 22)]);
    // The first day's midnight is before the first check, so its tick is the first check.
    expect(axis.ticks.map(label)).toEqual(["8/9:17", "9/0:0", "10/0:0"]);
  });

  it("labels both days of a two-day history", () => {
    const axis = timeAxis([at(10), at(11)], 10);
    expect(axis.domain).toEqual([at(10), at(11)]);
    expect(axis.ticks.map(label)).toEqual(["10/9:17", "11/0:0"]);
  });

  it("drops the first day's tick when it would crowd the next midnight", () => {
    const axis = timeAxis([at(10, 23, 50), at(11), at(12), at(13)], 10);
    expect(axis.ticks.map(label)).toEqual(["11/0:0", "12/0:0", "13/0:0"]);
  });

  it("skips whole days when they don't fit, and still never repeats a day", () => {
    const dates = Array.from({ length: 91 }, (_, i) => new Date(2026, 7, 13 + i, 9, 17));
    const axis = timeAxis(dates, 8);
    expect(axis.ticks.length).toBeLessThanOrEqual(8);
    const days = axis.ticks.map((d) => d.toDateString());
    expect(new Set(days).size).toBe(days.length);
    expect(axis.ticks.slice(1).every((d) => d.getHours() === 0 && d.getMinutes() === 0)).toBe(true);
    for (const tick of axis.ticks) {
      expect(tick >= axis.domain[0] && tick <= axis.domain[1]).toBe(true);
    }
  });

  it("shows the time of day when every check is on one day", () => {
    const axis = timeAxis([at(10, 9, 17), at(10, 9, 17), at(10, 14, 2), at(10, 21, 40)], 10);
    expect(axis.kind).toBe("time");
    expect(axis.ticks.map(label)).toEqual(["10/9:17", "10/14:2", "10/21:40"]);
  });

  it("thins check times that don't fit", () => {
    const dates = Array.from({ length: 12 }, (_, i) => at(10, 8 + i));
    expect(timeAxis(dates, 4).ticks.length).toBeLessThanOrEqual(4);
  });
});

describe("floorsOf", () => {
  const categories: Category[] = [
    { id: 1, name: "Skincare", parent_id: null, color: "#E8B4B8" },
    { id: 5, name: "Toners", parent_id: 1, color: "#E8B4B8" },
    { id: 6, name: "Serums", parent_id: 1, color: "#E8B4B8" },
    { id: 2, name: "Pantry", parent_id: null, color: "#C9D6A3" },
    { id: 3, name: "Cleaning", parent_id: null, color: "#A8C8E0" },
  ];

  it("keeps floor order, sorts by room then name, and collects products with no floor", () => {
    const products = [
      product({ id: 1, name: "B toner", category_id: 5 }),
      product({ id: 2, name: "A toner", category_id: 5 }),
      product({ id: 3, name: "Serum", category_id: 6 }),
      product({ id: 4, name: "Coffee", category_id: 2 }),
      product({ id: 5, name: "Mystery", category_id: null }),
    ];
    const floors = floorsOf(categories, products);
    expect(floors.map((f) => f.floor?.name ?? null)).toEqual(["Skincare", "Pantry", "Cleaning", null]);
    expect(floors[0].products.map((p) => p.name)).toEqual(["Serum", "A toner", "B toner"]);
    expect(floors[1].products.map((p) => p.name)).toEqual(["Coffee"]);
    expect(floors[2].products).toEqual([]);
    expect(floors[3].products.map((p) => p.name)).toEqual(["Mystery"]);
  });
});

describe("colour", () => {
  it("computes WCAG contrast", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 0);
    expect(contrast("#777777", "#777777")).toBe(1);
  });

  it("picks readable ink for any floor colour", () => {
    for (const bg of ["#E8B4B8", "#C9D6A3", "#A8C8E0", "#E6C9A8", "#1D3557", "#7A1F33", "#FFDD00"]) {
      expect(contrast(bg, inkOn(bg))).toBeGreaterThanOrEqual(4.5);
    }
  });
});

/** Every text/background pair the design uses, read straight from tokens.css. */
describe("tokens meet WCAG AA", () => {
  const css = readFileSync("src/styles/tokens.css", "utf8") // vitest runs from frontend/;
  const block = (selector: string) => {
    const start = css.indexOf(selector);
    const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
    return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
  };
  const night = block(":root");
  const quiet = { ...night, ...block(':root[data-mode="quiet"]') };

  it.each([
    ["night", "text", "bg"],
    ["night", "text-dim", "bg"],
    ["night", "ink", "paper"],
    ["night", "ink", "paper-faded"],
    ["night", "ink-placeholder", "paper"],
    ["night", "ink", "mustard"],
    ["night", "on-rouge", "rouge"],
    ["night", "subtitle-ink", "subtitle-bg"],
    ["night", "ink", "blind"],
    ["quiet", "text", "bg"],
    ["quiet", "text-dim", "bg"],
    ["quiet", "pencil", "bg"],
  ] as const)("%s: %s on %s", (mode, fg, bg) => {
    const tokens = mode === "night" ? night : quiet;
    expect(tokens[fg], fg).toBeDefined();
    expect(tokens[bg], bg).toBeDefined();
    expect(contrast(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(4.5);
  });

  // #C23B22 on the chart paper is 4.3:1: fine for the pencil arrow (a graphic,
  // 3:1), too low for text, so the notes themselves are written in ink.
  it("pencil marks on the chart paper stand out (3:1)", () => {
    expect(contrast(night.pencil, night.paper)).toBeGreaterThanOrEqual(3);
  });

  it("focus ring stands out (3:1) in both modes", () => {
    expect(contrast(night.focus, night.bg)).toBeGreaterThanOrEqual(3);
    expect(contrast(quiet.focus, quiet.bg)).toBeGreaterThanOrEqual(3);
  });
});
