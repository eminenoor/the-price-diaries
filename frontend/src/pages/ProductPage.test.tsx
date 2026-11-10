import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PricePoint, ProductDetail } from "../api";
import { ModeProvider } from "../mode";
import { ProductPage } from "./ProductPage";

const point = (checked_at: string, price: number, member_price: number | null = null): PricePoint => ({
  checked_at,
  price,
  member_price,
  currency: "TRY",
  in_stock: true,
});

export const detail = (overrides: Partial<ProductDetail> = {}): ProductDetail => ({
  id: 7,
  url: "https://www.gratis.com/x",
  name: "AHA BHA PHA 30 Days Miracle Toner 150 ml",
  brand: "Some By Mi",
  store: "gratis",
  category_id: null,
  target_price: null,
  image_url: null,
  last_error: null,
  blocked: false,
  created_at: "2026-11-01T09:00:00",
  summary: {
    current: 268.22,
    previous: 300,
    lowest: 268.22,
    lowest_at: "2026-11-10T09:17:00",
    highest: 320,
    highest_at: "2026-11-05T09:17:00",
    lowest_30d: 268.22,
    change_pct: -10.6,
    is_all_time_low: true,
    fake_sale: false,
  },
  regular_price: null,
  sparkline: [],
  history: [
    point("2026-11-05T09:17:00", 320),
    point("2026-11-08T09:17:00", 300),
    point("2026-11-10T09:17:00", 268.22),
  ],
  anomalies: [],
  ...overrides,
});

export function renderProduct(product: ProductDetail) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace("/api", "");
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      const data =
        path === "/stores"
          ? [{ key: "gratis", name: "Gratis", domains: [] }]
          : path === "/categories"
            ? []
            : method === "PATCH"
              ? { ...product, ...(body as object) }
              : product;
      return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModeProvider>
        <MemoryRouter initialEntries={[`/products/${product.id}`]}>
          <Routes>
            <Route path="/products/:id" element={<ProductPage />} />
          </Routes>
        </MemoryRouter>
      </ModeProvider>
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

export const firstCheck = (): Partial<ProductDetail> => ({
  summary: {
    current: 268.22,
    previous: null,
    lowest: 268.22,
    lowest_at: "2026-11-10T09:17:00",
    highest: 268.22,
    highest_at: "2026-11-10T09:17:00",
    lowest_30d: 268.22,
    change_pct: null,
    is_all_time_low: true,
    fake_sale: false,
  },
  history: [point("2026-11-10T09:17:00", 268.22)],
});

describe("ProductPage chart", () => {
  it("draws no chart for a single check, and says so in a note", async () => {
    renderProduct(detail(firstCheck()));
    expect(await screen.findByText("the chart starts after a few days of checks")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Price chart" })).not.toBeInTheDocument();
  });

  it("says only what one check can tell", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 10, 10, 20) });
    renderProduct(detail(firstCheck()));
    expect(await screen.findByText("First check today. Come back tomorrow to see if it moves.")).toBeInTheDocument();
    expect(screen.getByText("first check")).toBeInTheDocument();
    expect(screen.queryByText(/no change/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/lowest in 30 days/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Lowest")).not.toBeInTheDocument();
    expect(screen.queryByText("Highest")).not.toBeInTheDocument();
    // The price is in the hero and the one liner-notes track, nowhere else.
    expect(screen.getAllByText("268,22 lira")).toHaveLength(2);
    vi.useRealTimers();
  });

  it("draws the chart from two checks on", async () => {
    renderProduct(detail());
    expect(await screen.findByRole("region", { name: "Price chart" })).toBeInTheDocument();
    expect(screen.queryByText("the chart starts after a few days of checks")).not.toBeInTheDocument();
  });
});

describe("ProductPage stats", () => {
  it("has no stat boxes; the alert price is changed at the bottom", async () => {
    const calls = renderProduct(detail({ target_price: 250 }));
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector(".facts, .fact")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Change alert price" }));
    expect(screen.getByLabelText("Alert price")).toHaveValue("250");
    fireEvent.change(screen.getByLabelText("Alert price"), { target: { value: "240,50" } });
    fireEvent.click(screen.getByRole("button", { name: "Save alert price" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { target_price: 240.5 } }),
    );
  });

  it("says the alert price in words when there's no chart to write it on", async () => {
    renderProduct(detail({ ...firstCheck(), target_price: 250 }));
    expect(await screen.findByText(/^Alert price/)).toHaveTextContent("Alert price 250,00 lira");
  });

  it("asks for a real price", async () => {
    renderProduct(detail());
    fireEvent.click(await screen.findByRole("button", { name: "Set an alert price" }));
    fireEvent.change(screen.getByLabelText("Alert price"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save alert price" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a price, like 249,90.");
  });
});

describe("ProductPage window", () => {
  const windowOf = () => document.querySelector(".room__window .window");

  it("is lit with the curtains open for a good deal", async () => {
    renderProduct(detail());
    await screen.findByRole("heading", { level: 1 });
    expect(windowOf()).toHaveClass("window--lamp", "curtains--open");
  });

  it("is dark with the curtains closed after one check", async () => {
    renderProduct(detail(firstCheck()));
    await screen.findByRole("heading", { level: 1 });
    expect(windowOf()).toHaveClass("window--dark", "curtains--closed");
  });

  it("glows rose for a fake sale", async () => {
    const base = detail();
    renderProduct({ ...base, summary: { ...base.summary!, fake_sale: true } });
    await screen.findByRole("heading", { level: 1 });
    expect(windowOf()).toHaveClass("window--rose", "curtains--half");
  });
});

describe("ProductPage credit", () => {
  it("credits the brand, not the store", async () => {
    renderProduct(detail());
    expect(await screen.findByText("Some By Mi presents")).toBeInTheDocument();
    expect(screen.queryByText("Gratis presents")).not.toBeInTheDocument();
  });

  it("leaves the line out when the brand is unknown", async () => {
    renderProduct(detail({ brand: null }));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/presents$/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add the brand" })).toBeInTheDocument();
  });

  it("lets you change the brand", async () => {
    const calls = renderProduct(detail());
    fireEvent.click(await screen.findByRole("button", { name: "Change brand" }));
    fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "Some By Mi Lab" } });
    fireEvent.click(screen.getByRole("button", { name: "Save brand" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { brand: "Some By Mi Lab" } }),
    );
  });

  it("removes the brand when the field is cleared", async () => {
    const calls = renderProduct(detail());
    fireEvent.click(await screen.findByRole("button", { name: "Change brand" }));
    fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "  " } });
    fireEvent.click(screen.getByRole("button", { name: "Remove brand" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { brand: "" } }),
    );
  });
});
