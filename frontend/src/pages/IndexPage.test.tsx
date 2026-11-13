import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Category, Product } from "../api";
import { ModeProvider } from "../mode";
import { expectUnitPrice } from "../test-utils";
import { IndexPage } from "./IndexPage";

const CATEGORIES: Category[] = [
  { id: 1, name: "Skincare", parent_id: null, color: "#E8B4B8" },
  { id: 5, name: "Toners", parent_id: 1, color: "#E8B4B8" },
  { id: 6, name: "Moisturizers", parent_id: 1, color: "#E8B4B8" },
  { id: 2, name: "Pantry", parent_id: null, color: "#C9D6A3" },
];

const base = {
  url: "https://www.gratis.com/x",
  target_price: null,
  image_url: null,
  last_error: null,
  blocked: false,
  created_at: "2026-09-01T09:00:00",
  regular_price: null,
  size: null,
  unit_price: null,
  gtin: null,
  cheaper_elsewhere: null,
  sparkline: [],
  brand: null,
};
const summary = {
  current: 300,
  previous: 320,
  lowest: 300,
  lowest_at: "2026-11-10T09:00:00",
  highest: 360,
  highest_at: "2026-10-10T09:00:00",
  lowest_30d: 300,
  change_pct: -6.25,
  is_all_time_low: true,
  fake_sale: false,
};

export const PRODUCTS: Product[] = [
  { ...base, id: 3, name: "Zinc toner", store: "gratis", category_id: 5, summary },
  { ...base, id: 1, name: "Aloe toner", store: "gratis", category_id: 5, summary: { ...summary, change_pct: 0, is_all_time_low: false } },
  {
    ...base,
    id: 2,
    name: "Barrier cream",
    store: "sephora",
    category_id: 6,
    blocked: true,
    last_error: "www.sephora.com.tr blocks automated price checks (403).",
    summary: null,
  },
  { ...base, id: 4, name: "Coffee", store: "amazon", category_id: 2, summary: null },
];

function mockApi(products: Product[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).replace("/api", "");
      const data =
        path === "/products"
          ? products
          : path === "/categories"
            ? CATEGORIES
            : [
                { key: "gratis", name: "Gratis", domains: [] },
                { key: "sephora", name: "Sephora", domains: [] },
                { key: "amazon", name: "Amazon", domains: [] },
              ];
      return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
    }),
  );
}

export function renderIndex(products: Product[], route = "/") {
  mockApi(products);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModeProvider>
        <MemoryRouter initialEntries={[route]}>
          <IndexPage />
        </MemoryRouter>
      </ModeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("IndexPage states", () => {
  it("shows a dark building when nothing is tracked", async () => {
    renderIndex([]);
    expect(await screen.findByRole("heading", { name: "no lights on yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pin a new window" })).toHaveAttribute("href", "/add");
  });

  it("pulls the blinds down on a blocked store and says why in words", async () => {
    renderIndex(PRODUCTS);
    const link = await screen.findByRole("link", { name: /Barrier cream/ });
    expect(link).toHaveTextContent("Sephora doesn't allow automated checks");
    expect(link.closest("li")?.querySelector(".blinds")).not.toBeNull();
  });

  it("stacks every floor in the everything view, and says when a floor is empty", async () => {
    renderIndex(PRODUCTS.filter((p) => p.category_id !== 2));
    const skincare = await screen.findByRole("region", { name: "skincare" });
    expect(within(skincare).getAllByRole("listitem")).toHaveLength(3);
    const pantry = screen.getByRole("region", { name: "pantry" });
    expect(pantry).toHaveTextContent("No lights on this floor yet.");
  });

  it("says an empty floor is empty once, and subtitles the whole building", async () => {
    renderIndex(PRODUCTS.filter((p) => p.category_id !== 2), "/?floor=2");
    expect(await screen.findByText("No lights on this floor yet.")).toBeInTheDocument();
    expect(screen.queryByText(/^No lights on yet/)).not.toBeInTheDocument();
    expect(document.querySelector(".subtitle")).toHaveTextContent(
      "Zinc toner is at its lowest ever at Gratis.",
    );
  });

  it("titles quiet mode with the full name", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderIndex(PRODUCTS);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("the price diaries");
  });

  it("titles the empty quiet poster with the full name too", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderIndex([]);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("the price diaries");
  });

  it("does the same in quiet mode", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderIndex(PRODUCTS.filter((p) => p.category_id !== 2), "/?floor=2");
    expect(await screen.findByText("Nothing tracked on this floor yet.")).toBeInTheDocument();
    expect(document.querySelector(".poster-summary")).toHaveTextContent(
      "Zinc toner is at its lowest ever at Gratis.",
    );
  });
});

describe("IndexPage unit prices", () => {
  const sized = PRODUCTS.map((p) =>
    p.id === 3
      ? {
          ...p,
          size: { amount: 150, unit: "ml" as const, source: "name" as const },
          unit_price: { price: 25.3, per: 10, unit: "ml" as const },
        }
      : p,
  );

  it("writes the price per 10 ml under the price in night view", async () => {
    renderIndex(sized);
    const link = await screen.findByRole("link", { name: /Zinc toner/ });
    expectUnitPrice(link.querySelector(".unit-price"), "25,30", "10 ml");
    // Without a size there's no unit price.
    expect(screen.getByRole("link", { name: /Aloe toner/ }).querySelector(".unit-price")).toBeNull();
  });

  it("does the same in quiet mode", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderIndex(sized);
    const link = await screen.findByRole("link", { name: /Zinc toner/ });
    expectUnitPrice(link.querySelector(".unit-price"), "25,30", "10 ml");
  });
});

const NOTE = { product_id: 9, store: "watsons", store_name: "Watsons", saving: 40 };

/** Zinc toner and the blocked Barrier cream are cheaper at Watsons today. */
function withNote(): Product[] {
  return PRODUCTS.map((p) => (p.id === 3 || p.id === 2 ? { ...p, cheaper_elsewhere: NOTE } : p));
}

describe("IndexPage cheaper elsewhere", () => {
  it("notes a cheaper store under the price in night view", async () => {
    renderIndex(withNote());
    const link = await screen.findByRole("link", { name: /Zinc toner/ });
    const note = link.querySelector(".cheaper-elsewhere");
    expect(note).toHaveTextContent("40,00 lira");
    expect(note).toHaveTextContent("cheaper at Watsons");
    expect(screen.getByRole("link", { name: /Aloe toner/ }).querySelector(".cheaper-elsewhere")).toBeNull();
    // A blocked store's window only says why it's blocked.
    expect(screen.getByRole("link", { name: /Barrier cream/ }).querySelector(".cheaper-elsewhere")).toBeNull();
  });

  it("does the same in quiet mode", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderIndex(withNote());
    const link = await screen.findByRole("link", { name: /Zinc toner/ });
    expect(link.querySelector(".cheaper-elsewhere")).toHaveTextContent("cheaper at Watsons");
  });
});
