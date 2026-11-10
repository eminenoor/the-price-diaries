import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Category, Product } from "../api";
import { ModeProvider } from "../mode";
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
  sparkline: [],
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

afterEach(() => vi.unstubAllGlobals());

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
});
