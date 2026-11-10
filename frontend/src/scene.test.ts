/// <reference types="node" />
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { Category, Product, Summary } from "./api";
import {
  contrast,
  floorsOf,
  inkOn,
  newsLine,
  placement,
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
  sparkline: [],
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
  ];
  it.each(cases)("%s", (_, overrides, kind, words) => {
    expect(windowState(product(overrides), "Gratis")).toEqual({ kind, words });
  });
});

describe("newsLine", () => {
  const deal = product({ id: 1, name: "Toner", summary: summary({ change_pct: -7, is_all_time_low: true }) });
  const fake = product({ id: 2, name: "Sunscreen", store: "watsons", summary: summary({ fake_sale: true }) });
  const fake2 = product({ id: 3, name: "Laundry liquid", summary: summary({ fake_sale: true }) });
  const steady = product({ id: 4, name: "Coffee" });

  it("leads with the best deal and warns about fake sales in one sentence", () => {
    expect(newsLine([steady, fake, deal], storeName)).toBe(
      "Toner is the lowest it's ever been at Gratis, but one sale tonight is fake.",
    );
    expect(newsLine([deal, fake, fake2], storeName)).toMatch(/but 2 sales tonight are fake\.$/);
  });

  it("names a single fake sale", () => {
    expect(newsLine([fake, steady], storeName)).toBe(
      "The sale on Sunscreen at Watsons is fake: the price went up first.",
    );
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
      expect(p.size).toBeGreaterThanOrEqual(0.78);
      expect(p.size).toBeLessThanOrEqual(1);
      expect(Math.abs(p.nudge)).toBeLessThanOrEqual(1);
      expect(p.drop).toBeGreaterThanOrEqual(0);
      expect(p.drop).toBeLessThanOrEqual(56);
    }
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
    ["night", "text", "facade"],
    ["night", "text-dim", "facade"],
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

  it("focus ring stands out (3:1) in both modes", () => {
    expect(contrast(night.focus, night.bg)).toBeGreaterThanOrEqual(3);
    expect(contrast(quiet.focus, quiet.bg)).toBeGreaterThanOrEqual(3);
  });
});
