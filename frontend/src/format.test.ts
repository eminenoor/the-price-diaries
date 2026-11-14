import { describe, expect, it } from "vitest";

import type { Product, Summary } from "./api";
import {
  formatBasis,
  formatChange,
  formatCheck,
  formatPrice,
  formatSize,
  insight,
  pickFeature,
} from "./format";

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
  name: "Serum",
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
  listing_name: "Store name",
  cheaper_elsewhere: null,
  sparkline: [],
  brand: null,
  ...overrides,
});

describe("formatPrice", () => {
  it("uses Turkish grouping and decimal comma", () => {
    expect(formatPrice(1299.9)).toBe("1.299,90");
  });
});

describe("formatBasis", () => {
  it("says what a unit price is for", () => {
    expect(formatBasis(10, "ml")).toBe("10 ml");
    expect(formatBasis(100, "g")).toBe("100 g");
    expect(formatBasis(1, "pcs")).toBe("piece");
  });
});

describe("formatSize", () => {
  it("writes a size the way a pack prints it", () => {
    expect(formatSize({ amount: 150, unit: "ml" })).toBe("150 ml");
    expect(formatSize({ amount: 1500, unit: "ml" })).toBe("1,5 L");
    expect(formatSize({ amount: 1000, unit: "g" })).toBe("1 kg");
    expect(formatSize({ amount: 2500, unit: "g" })).toBe("2,5 kg");
    expect(formatSize({ amount: 60, unit: "pcs" })).toBe("60 pieces");
    expect(formatSize({ amount: 1, unit: "pcs" })).toBe("1 piece");
  });
});

describe("formatCheck", () => {
  it("writes date, time and a Turkish price, the way the chart tooltip shows it", () => {
    expect(formatCheck(new Date(2026, 10, 10, 9, 17), 268.22)).toBe("10 Nov, 09:17 · ₺268,22");
    expect(formatCheck(new Date(2026, 0, 3, 21, 5), 1299.9)).toBe("3 Jan, 21:05 · ₺1.299,90");
  });
});

describe("formatChange", () => {
  it("uses a true minus sign for drops", () => {
    expect(formatChange(-8.24)).toBe("−8.2%");
    expect(formatChange(12)).toBe("+12.0%");
  });
});

describe("insight", () => {
  it("warns about fake sales before anything else", () => {
    const p = product({ target_price: 400, summary: summary({ fake_sale: true }) });
    expect(insight(p)).toMatch(/isn't really cheaper/);
  });

  it("celebrates hitting the target", () => {
    expect(insight(product({ target_price: 310 }))).toMatch(/Below your alert price/);
  });

  it("reports failed checks", () => {
    expect(insight(product({ last_error: "Store answered 503." }))).toBe(
      "Last check failed: Store answered 503.",
    );
  });

  it("asks you to come back after the first check", () => {
    const one = summary({ previous: null, change_pct: null, current: 250, lowest: 250, lowest_30d: 250, lowest_at: "2026-11-11T09:17:00" });
    expect(insight(product({ summary: one }), new Date(2026, 10, 11, 20))).toBe(
      "First check today. Come back tomorrow to see if it moves.",
    );
    expect(insight(product({ summary: one }), new Date(2026, 10, 13))).toBe(
      "First check on 11 Nov. The next check shows if it moves.",
    );
    expect(insight(product({ summary: one, target_price: 300 }))).toMatch(/^Below your alert price/);
  });

  it("doesn't call a price that never moved the lowest", () => {
    const flat = summary({ current: 300, lowest: 300, highest: 300, lowest_30d: 300, is_all_time_low: true });
    expect(insight(product({ summary: flat }))).not.toMatch(/lowest price since/);
    const low = summary({ current: 250, lowest: 250, lowest_30d: 250, is_all_time_low: true });
    expect(insight(product({ summary: low }))).toBe("The lowest price since you started tracking.");
  });

  it("handles products that were never checked", () => {
    expect(insight(product({ summary: null }))).toBe("Waiting for the first price check.");
  });
});

describe("pickFeature", () => {
  it("prefers a real all-time low over a fake sale", () => {
    const fake = product({ id: 1, summary: summary({ current: 200, fake_sale: true }) });
    const real = product({ id: 2, summary: summary({ current: 250, is_all_time_low: true }) });
    expect(pickFeature([fake, real])?.id).toBe(2);
  });
});
