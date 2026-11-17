import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Paper } from "../api";
import { ModeProvider } from "../mode";
import { PaperPage } from "./PaperPage";

const AT = "2026-11-12T09:17:00";

const paper = (overrides: Partial<Paper> = {}): Paper => ({
  week_start: "2026-11-09",
  week_end: "2026-11-15",
  previous_week: "2026-11-02",
  next_week: null,
  products_checked: 16,
  drops: [],
  new_lows: [],
  fake_sales: [],
  cheaper: [],
  rises: [],
  trouble: [],
  ...overrides,
});

const FULL = paper({
  drops: [
    { product_id: 1, name: "Vitamin C Serum", store_name: "Eve Shop", old_price: 399, new_price: 351.12, change_pct: -12 },
    { product_id: 2, name: "Olive Oil", store_name: "Trendyol", old_price: 610, new_price: 580, change_pct: -4.92 },
  ],
  new_lows: [{ product_id: 1, name: "Vitamin C Serum", store_name: "Eve Shop", price: 351.12, at: AT, previous_low: 360 }],
  fake_sales: [{ product_id: 3, name: "Laundry Liquid", store_name: "Rossmann", price: 289, peak: 361.25, at: AT }],
  cheaper: [
    {
      product_id: 3,
      name: "Laundry Liquid",
      store_name: "Rossmann",
      other_store_name: "Trendyol",
      price_here: 289,
      price_there: 275,
      at: AT,
    },
  ],
  rises: [{ product_id: 4, name: "Cleanser", store_name: "Rossmann", old_price: 159, new_price: 163.77, change_pct: 3 }],
  trouble: [
    {
      product_id: 5,
      name: "Barrier Cream",
      store_name: "Sephora",
      failed_checks: 3,
      last_error: "www.sephora.com.tr blocks automated price checks.",
      out_of_stock_at: null,
    },
    { product_id: 6, name: "Vitamin D3", store_name: "Gratis", failed_checks: 0, last_error: null, out_of_stock_at: AT },
  ],
});

function renderPaper(data: Paper, path = "/paper") {
  const asked: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      asked.push(String(input));
      return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModeProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/paper" element={<PaperPage />} />
          </Routes>
        </MemoryRouter>
      </ModeProvider>
    </QueryClientProvider>,
  );
  return asked;
}

/** The text a screen reader hears: without the aria-hidden pieces, spaces tidied. */
function heard(element: Element): string {
  const copy = element.cloneNode(true) as Element;
  copy.querySelectorAll("[aria-hidden='true']").forEach((e) => e.remove());
  return (copy.textContent ?? "").replace(/\s+/g, " ").trim();
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("the Sunday paper", () => {
  it("names the week in the masthead", async () => {
    renderPaper(FULL);
    const title = await screen.findByRole("heading", { level: 1 });
    expect(heard(title)).toBe("the sunday paper");
    const article = screen.getByRole("article", { name: "the sunday paper" });
    expect(article).toHaveTextContent("The week of 9 to 15 November 2026");
    expect(article).toHaveTextContent("16 products checked");
  });

  it("leads with the biggest drop", async () => {
    renderPaper(FULL);
    const lead = await screen.findByRole("region", { name: "Vitamin C Serum down 12.0%" });
    expect(heard(lead)).toContain("351,12 lira at Eve Shop, was 399,00 lira");
    expect(within(lead).getByRole("link", { name: "Vitamin C Serum" })).toHaveAttribute("href", "/products/1");
  });

  it("writes every section in words, in reading order", async () => {
    renderPaper(FULL);
    await screen.findByRole("heading", { level: 1 });
    const titles = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual([
      "Vitamin C Serum down 12.0%",
      "more drops",
      "new lows",
      "fake sales caught",
      "cheaper elsewhere",
      "price rises",
      "failed checks and sold out",
    ]);
    const line = (section: string) =>
      Array.from(screen.getByRole("region", { name: section }).querySelectorAll("li"), (li) => heard(li));
    expect(line("more drops")).toEqual(["Olive Oil at Trendyol, down 4.9%: 610,00 lira to 580,00 lira."]);
    expect(line("new lows")).toEqual([
      "Vitamin C Serum at Eve Shop: 351,12 lira on 12 Nov, under the old low of 360,00 lira.",
    ]);
    expect(line("fake sales caught")).toEqual([
      "Laundry Liquid at Rossmann: “on sale” at 289,00 lira on 12 Nov, after a rise to 361,25 lira.",
    ]);
    expect(line("cheaper elsewhere")).toEqual([
      "Laundry Liquid: 275,00 lira at Trendyol, 289,00 lira at Rossmann, on 12 Nov.",
    ]);
    expect(line("price rises")).toEqual(["Cleanser at Rossmann, up 3.0%: 159,00 lira to 163,77 lira."]);
    expect(line("failed checks and sold out")).toEqual([
      "Barrier Cream at Sephora: 3 checks failed (www.sephora.com.tr blocks automated price checks).",
      "Vitamin D3 at Gratis: Sold out from 12 Nov.",
    ]);
  });

  it("renders every price with the Price component", async () => {
    renderPaper(FULL);
    const lows = await screen.findByRole("region", { name: "new lows" });
    expect(lows.querySelectorAll(".price")).toHaveLength(2);
  });

  it("skips empty sections", async () => {
    renderPaper(paper({ rises: FULL.rises }));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["price rises"]);
  });

  it("says a quiet week in one calm line", async () => {
    renderPaper(paper());
    expect(
      await screen.findByText("A quiet week. No price moved, and every check went through."),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole("heading", { level: 2 })).toHaveLength(0);
  });

  it("opens the week before and after", async () => {
    const asked = renderPaper(paper({ next_week: "2026-11-16" }), "/paper?week=2026-11-12");
    const nav = await screen.findByRole("navigation", { name: "Other weeks" });
    expect(within(nav).getByRole("link", { name: "Previous week" })).toHaveAttribute(
      "href",
      "/paper?week=2026-11-02",
    );
    expect(within(nav).getByRole("link", { name: "Next week" })).toHaveAttribute("href", "/paper?week=2026-11-16");
    expect(asked).toEqual(["/api/paper?week=2026-11-12"]);
  });

  it("has no next week before the next paper is out", async () => {
    const asked = renderPaper(paper());
    await screen.findByRole("navigation", { name: "Other weeks" });
    expect(screen.queryByRole("link", { name: "Next week" })).toBeNull();
    expect(asked).toEqual(["/api/paper"]);
  });

  it("prints the page", async () => {
    const print = vi.fn();
    vi.stubGlobal("print", print);
    renderPaper(FULL);
    (await screen.findByRole("button", { name: "Print this page" })).click();
    expect(print).toHaveBeenCalledOnce();
  });

  it("marks only the items past five as screen-only, and says how many more on paper", async () => {
    const drops = Array.from({ length: 8 }, (_, i) => ({
      product_id: i + 1,
      name: `Product ${i + 1}`,
      store_name: "Gratis",
      old_price: 100,
      new_price: 90 - i,
      change_pct: -(10 + i),
    }));
    renderPaper(paper({ drops }));
    const more = await screen.findByRole("region", { name: "more drops" });
    expect(more.querySelectorAll("li")).toHaveLength(7);
    expect(more.querySelectorAll("li.paper-list__extra")).toHaveLength(2);
    expect(more.querySelector(".paper-list__more")).toHaveTextContent("and 2 more");
  });

  it("keeps handwritten notes out of the accessibility tree", async () => {
    renderPaper(FULL);
    await screen.findByRole("heading", { level: 1 });
    const notes = document.querySelectorAll(".paper-hand");
    expect(notes.length).toBeGreaterThan(0);
    notes.forEach((note) => expect(note).toHaveAttribute("aria-hidden", "true"));
  });

  it("tilts the sheet a little at night only", async () => {
    renderPaper(FULL);
    const article = await screen.findByRole("article");
    expect(Math.abs(parseFloat(article.style.getPropertyValue("--tilt")))).toBeLessThanOrEqual(3);
  });

  it("doesn't tilt in quiet mode", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderPaper(FULL);
    const article = await screen.findByRole("article");
    expect(article.style.getPropertyValue("--tilt")).toBe("");
  });
});
