import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Category, Offer, PricePoint, Product, ProductDetail } from "../api";
import { ModeProvider } from "../mode";
import { expectUnitPrice } from "../test-utils";
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
  size: null,
  unit_price: null,
  gtin: null,
  listing_name: "Store name",
  cheaper_elsewhere: null,
  sparkline: [],
  history: [
    point("2026-11-05T09:17:00", 320),
    point("2026-11-08T09:17:00", 300),
    point("2026-11-10T09:17:00", 268.22),
  ],
  anomalies: [],
  elsewhere: [],
  linked_ids: [],
  best_time: {
    enough_history: false,
    days_of_month: [],
    weekdays: [],
    sale_cycle: null,
    events: [],
    backtest: null,
  },
  ...overrides,
});

export function renderProduct(product: ProductDetail, others: Product[] = [], categories: Category[] = []) {
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
            ? categories
            : path === "/products"
              ? [product, ...others]
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

describe("ProductPage best time to buy", () => {
  const paydays = {
    enough_history: true,
    days_of_month: [1, 15],
    weekdays: [],
    sale_cycle: { every_days: 35, typical_pct: 15.2, last_days_ago: 21 },
    events: [{ name: "Efsane Cuma" as const, pct: 18.4 }],
    backtest: { trials: 103, wins: 86, average_saving_pct: 9.5 },
  };

  afterEach(() => localStorage.clear());

  it("says when it has been cheapest, and how waiting would have done", async () => {
    renderProduct(detail({ best_time: paydays }));
    const section = await screen.findByRole("region", { name: "best time to buy" });
    expect(section).toHaveTextContent(
      "Has usually been cheapest around the 1st and 15th. Real sales have come every ~5 weeks, " +
        "usually 15% off; the last one 3 weeks ago. Efsane Cuma was 18% off.",
    );
    expect(section).toHaveTextContent("Looking back, waiting for these times paid less on 86 of 103 days, 9.5% less on average.");
    // Taped up at night, tilted by at most 3 degrees.
    const note = section.querySelector<HTMLElement>(".best-time__note")!;
    expect(Math.abs(parseFloat(note.style.getPropertyValue("--tilt")))).toBeLessThanOrEqual(3);
  });

  it("says when there isn't enough history yet, with no backtest", async () => {
    renderProduct(detail());
    const section = await screen.findByRole("region", { name: "best time to buy" });
    expect(section).toHaveTextContent("Not enough history yet.");
    expect(section).not.toHaveTextContent("Looking back");
  });

  it("is a plain note in quiet mode, with no tilt", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderProduct(detail({ best_time: paydays }));
    const section = await screen.findByRole("region", { name: "best time to buy" });
    expect(section.querySelector<HTMLElement>(".best-time__note")!.style.getPropertyValue("--tilt")).toBe("");
    expect(section).toHaveTextContent("Has usually been cheapest around the 1st and 15th.");
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

describe("ProductPage size", () => {
  const sized = (): Partial<ProductDetail> => ({
    size: { amount: 150, unit: "ml", source: "name" },
    unit_price: { price: 17.88, per: 10, unit: "ml" },
  });

  it("writes the price per 10 ml under the price, and the size", async () => {
    renderProduct(detail(sized()));
    expect(await screen.findByText("Size 150 ml")).toBeInTheDocument();
    expectUnitPrice(document.querySelector(".room__price .unit-price"), "17,88", "10 ml");
  });

  it("changes the size as typed, with a decimal comma", async () => {
    const calls = renderProduct(detail(sized()));
    fireEvent.click(await screen.findByRole("button", { name: "Change size" }));
    const input = screen.getByRole("textbox", { name: "Size" });
    expect(input).toHaveValue("150 ml");
    fireEvent.change(input, { target: { value: "1,5 L" } });
    fireEvent.click(screen.getByRole("button", { name: "Save size" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { size: "1,5 L" } }),
    );
  });

  it("offers to add a size when there is none, and to remove one", async () => {
    const calls = renderProduct(detail());
    fireEvent.click(await screen.findByRole("button", { name: "Add the size" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove size" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { size: "" } }),
    );
  });

  it("says why a size wasn't saved", async () => {
    renderProduct(detail(sized()));
    fireEvent.click(await screen.findByRole("button", { name: "Change size" }));
    const message = "Write the size with a unit, like 150 ml, 1,5 L, 500 g or 60 adet.";
    const ok = globalThis.fetch;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === "PATCH"
          ? new Response(JSON.stringify({ detail: message }), { status: 422 })
          : ok(input, init),
      ),
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Size" }), { target: { value: "150" } });
    fireEvent.click(screen.getByRole("button", { name: "Save size" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("textbox", { name: "Size" })).toBeInTheDocument();
  });
});

describe("ProductPage elsewhere", () => {
  const offer = (overrides: Partial<Offer>): Offer => ({
    product_id: 8,
    name: "Toner 150 ml",
    store: "watsons",
    store_name: "Watsons",
    price: 229.33,
    unit_price: { price: 15.29, per: 10, unit: "ml" },
    checked_at: "2026-11-10T09:17:00",
    in_stock: true,
    saving: 38.89,
    ...overrides,
  });
  const twoStores = () =>
    detail({
      elsewhere: [
        offer({}),
        offer({ product_id: 9, store: "rossmann", store_name: "Rossmann", price: 280.22, saving: -12, unit_price: null }),
      ],
      linked_ids: [8, 9],
    });

  it("lists the same product at other stores, cheapest first, compared with this one", async () => {
    renderProduct(twoStores());
    const section = await screen.findByRole("region", { name: "elsewhere" });
    const rows = within(section).getAllByRole("listitem");
    expect(rows.map((r) => within(r).getByRole("link").textContent)).toEqual([
      "Watsons, Toner 150 ml",
      "Rossmann, Toner 150 ml",
    ]);
    expect(rows[0]).toHaveTextContent("38,89 lira");
    expect(rows[0]).toHaveTextContent(/cheaper/);
    expectUnitPrice(rows[0].querySelector(".unit-price"), "15,29", "10 ml");
    expect(rows[1]).toHaveTextContent("12,00 lira");
    expect(rows[1]).toHaveTextContent(/more/);
    expect(within(rows[0]).getByRole("link")).toHaveAttribute("href", "/products/8");
  });

  it("unlinks a listing that isn't the same product", async () => {
    const calls = renderProduct(twoStores());
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(within(section).getByRole("button", { name: "Not the same product at Rossmann" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "DELETE", path: "/products/9/link", body: undefined }),
    );
  });

  it("links another tracked product by hand", async () => {
    const other = { ...detail({ id: 12, store: "watsons", name: "Miracle Toner" }) };
    const calls = renderProduct(detail(), [other]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    expect(section).toHaveTextContent("Not tracked at another store yet.");
    // The form stays out of the way until asked for.
    expect(within(section).queryByRole("combobox")).not.toBeInTheDocument();
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    const select = within(section).getByRole("combobox", { name: "Same product at" });
    fireEvent.change(select, { target: { value: "12" } });
    fireEvent.click(within(section).getByRole("button", { name: "Link products" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "POST", path: "/products/7/link", body: { other_id: 12 } }),
    );
  });

  it("doesn't offer products that are already linked, or itself", async () => {
    renderProduct(twoStores(), [detail({ id: 8 }), detail({ id: 9 })]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    await screen.findAllByRole("listitem");
    expect(within(section).queryByRole("button", { name: "Link another store" })).not.toBeInTheDocument();
  });

  it("doesn't offer a linked product that hasn't been checked yet", async () => {
    renderProduct(detail({ linked_ids: [12] }), [detail({ id: 12 }), detail({ id: 13, listing_name: "Other" })]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    const values = within(section)
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value);
    expect(values).toEqual(["", "13"]);
  });

  it("starts on choose a product, with the link button off until one is picked", async () => {
    renderProduct(detail(), [detail({ id: 12, store: "watsons" })]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    const select = within(section).getByRole("combobox", { name: "Same product at" });
    expect(select).toHaveDisplayValue("choose a product");
    const button = within(section).getByRole("button", { name: "Link products" });
    expect(button).toBeDisabled();
    fireEvent.change(select, { target: { value: "12" } });
    expect(button).toBeEnabled();
  });

  it("lists the same room first, then the rest by floor", async () => {
    const categories: Category[] = [
      { id: 1, name: "Skincare", parent_id: null, color: "#E8B4B8" },
      { id: 5, name: "Toners", parent_id: 1, color: "#E8B4B8" },
      { id: 2, name: "Bath", parent_id: null, color: "#A8C8E0" },
    ];
    renderProduct(
      detail({ category_id: 5 }),
      [
        detail({ id: 12, name: "Soap", listing_name: "Soap", category_id: 2 }),
        detail({ id: 13, name: "Toner", listing_name: "Toner", category_id: 5 }),
      ],
      categories,
    );
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    const groups = within(section).getAllByRole("group");
    expect(groups.map((g) => g.getAttribute("label"))).toEqual(["Same room (Toners)", "Bath"]);
    expect(within(groups[0]).getByRole("option")).toHaveTextContent("Toner");
    expect(within(groups[1]).getByRole("option")).toHaveTextContent("Soap");
  });

  it("closes the link form again on cancel", async () => {
    renderProduct(detail(), [detail({ id: 12, store: "watsons" })]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    fireEvent.click(within(section).getByRole("button", { name: "Cancel" }));
    expect(within(section).queryByRole("combobox")).not.toBeInTheDocument();
    expect(within(section).getByRole("button", { name: "Link another store" })).toBeInTheDocument();
  });

  it("lists each store's own name to link", async () => {
    renderProduct(detail(), [detail({ id: 12, store: "watsons", listing_name: "Watsons title" })]);
    const section = await screen.findByRole("region", { name: "elsewhere" });
    fireEvent.click(await within(section).findByRole("button", { name: "Link another store" }));
    expect(within(section).getByRole("option", { name: "watsons: Watsons title" })).toBeInTheDocument();
  });
});

describe("ProductPage name", () => {
  it("renames the product for every store in its group", async () => {
    const calls = renderProduct(detail({ elsewhere: [] }));
    fireEvent.click(await screen.findByRole("button", { name: "Change name" }));
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input).toHaveValue("AHA BHA PHA 30 Days Miracle Toner 150 ml");
    fireEvent.change(input, { target: { value: "My toner" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { display_name: "My toner" } }),
    );
  });

  it("goes back to the store's name when cleared", async () => {
    const calls = renderProduct(detail());
    fireEvent.click(await screen.findByRole("button", { name: "Change name" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Use the store's name" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "PATCH", path: "/products/7", body: { display_name: "" } }),
    );
  });
});
