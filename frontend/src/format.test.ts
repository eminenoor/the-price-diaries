import { describe, expect, it } from "vitest";

import type { Product, Summary } from "./api";
import { formatChange, formatPrice, insight, pickFeature } from "./format";

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
  sparkline: [],
  ...overrides,
});

describe("formatPrice", () => {
  it("uses Turkish grouping and decimal comma", () => {
    expect(formatPrice(1299.9)).toBe("1.299,90");
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
