import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TopBar } from "../App";
import type { Note } from "../api";
import { ModeProvider } from "../mode";
import { NotesPage } from "./NotesPage";

const note = (overrides: Partial<Note> = {}): Note => ({
  id: 1,
  kind: "lowest",
  product_id: 7,
  product_name: "Miracle Toner",
  store: "gratis",
  store_name: "Gratis",
  old_price: 300,
  new_price: 268.22,
  other_store_name: null,
  week: null,
  created_at: "2026-11-15T09:17:00",
  read: false,
  ...overrides,
});

const PAPER_NOTE = note({
  id: 6,
  kind: "sunday_paper",
  product_id: null,
  product_name: null,
  store: null,
  store_name: null,
  old_price: null,
  new_price: null,
  week: "2026-11-09",
});

const NOTES: Note[] = [
  note(),
  note({ id: 2, kind: "fake_sale", old_price: 437.5, new_price: 349, read: true }),
  note({ id: 3, kind: "cheaper", old_price: 494, new_price: 340, other_store_name: "Watsons" }),
  note({ id: 4, kind: "back_in_stock", old_price: 420, new_price: 420 }),
  note({ id: 5, kind: "target", old_price: 300, new_price: 249.9 }),
];

function renderNotes(notes: Note[], path = "/notes") {
  const calls: { method: string; path: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const p = String(input).replace("/api", "");
      calls.push({ method: init?.method ?? "GET", path: p });
      const data =
        p === "/notifications"
          ? { unread: notes.filter((n) => !n.read).length, notes }
          : p === "/products"
            ? []
            : null;
      return data === null
        ? new Response(null, { status: 204 })
        : new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModeProvider>
        <MemoryRouter initialEntries={[path]}>
          <TopBar />
          <Routes>
            <Route path="/notes" element={<NotesPage />} />
            <Route path="/products/:id" element={<p>product page</p>} />
          </Routes>
        </MemoryRouter>
      </ModeProvider>
    </QueryClientProvider>,
  );
  return calls;
}

/** The text a screen reader hears: without the aria-hidden price pieces, spaces tidied. */
function heard(element: Element): string {
  const copy = element.cloneNode(true) as Element;
  copy.querySelectorAll("[aria-hidden='true']").forEach((e) => e.remove());
  return (copy.textContent ?? "").replace(/\s+/g, " ").trim();
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("notes", () => {
  it("shows the unread count in the header, in words", async () => {
    renderNotes(NOTES);
    const link = await screen.findByRole("link", { name: "Notes, 4 new" });
    expect(link).toHaveAttribute("href", "/notes");
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("shows just Notes when everything is read", async () => {
    renderNotes([note({ read: true })]);
    expect(await screen.findByText("All notes read.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notes" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark all as read" })).toBeNull();
  });

  it("writes each note as a sentence with the prices, linked to its product", async () => {
    renderNotes(NOTES);
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(5);

    const [lowest, fake, cheaper, stock, target] = items;
    const sentence = (item: HTMLElement) => heard(item.querySelector(".inbox-note__text")!);
    expect(heard(lowest.querySelector(".inbox-note__head")!)).toBe("lowest ever new");
    expect(sentence(lowest)).toBe(
      "Miracle Toner at Gratis is now 268,22 lira (was 300,00 lira), the lowest since you started tracking.",
    );
    expect(within(lowest).getByRole("link", { name: "Miracle Toner" })).toHaveAttribute(
      "href",
      "/products/7",
    );
    expect(heard(fake.querySelector(".inbox-note__head")!)).toBe("fake sale read");
    expect(sentence(fake)).toBe(
      "Miracle Toner at Gratis is now 349,00 lira (was 437,50 lira), but only after a recent price rise. Not really cheaper.",
    );
    expect(sentence(cheaper)).toBe(
      "Miracle Toner is 340,00 lira at Watsons for the same amount, 494,00 lira at Gratis.",
    );
    expect(sentence(stock)).toBe("Miracle Toner is back in stock at Gratis, now 420,00 lira.");
    expect(sentence(target)).toBe(
      "Miracle Toner at Gratis is now 249,90 lira (was 300,00 lira), at or under your alert price.",
    );
    expect(within(lowest).getByText("15 Nov, 09:17")).toHaveAttribute("datetime", "2026-11-15T09:17:00");
  });

  it("says the Sunday paper is ready, linked to that week's paper", async () => {
    renderNotes([PAPER_NOTE]);
    const [item] = await screen.findAllByRole("listitem");
    expect(heard(item.querySelector(".inbox-note__head")!)).toBe("sunday paper new");
    expect(heard(item.querySelector(".inbox-note__text")!)).toBe(
      "Your Sunday paper is ready: the week of 9 to 15 Nov, on one page.",
    );
    expect(within(item).getByRole("link", { name: "Your Sunday paper is ready" })).toHaveAttribute(
      "href",
      "/paper?week=2026-11-09",
    );
  });

  it("renders every price with the Price component", async () => {
    renderNotes(NOTES);
    const [lowest] = await screen.findAllByRole("listitem");
    expect(lowest.querySelectorAll(".price")).toHaveLength(2);
  });

  it("marks one note as read", async () => {
    const calls = renderNotes(NOTES);
    const [lowest, fake] = await screen.findAllByRole("listitem");
    expect(within(fake).queryByRole("button", { name: "Mark as read" })).toBeNull();
    fireEvent.click(within(lowest).getByRole("button", { name: "Mark as read" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "POST", path: "/notifications/1/read" }),
    );
  });

  it("marks all notes as read", async () => {
    const calls = renderNotes(NOTES);
    expect(await screen.findByText("4 new notes.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() => expect(calls).toContainEqual({ method: "POST", path: "/notifications/read" }));
  });

  it("says what the inbox is for when it's empty", async () => {
    renderNotes([]);
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notes" })).toBeInTheDocument();
  });

  it("tilts notes at night only, and never more than 3 degrees", async () => {
    renderNotes(NOTES);
    const items = await screen.findAllByRole("listitem");
    for (const item of items) {
      const tilt = parseFloat(item.style.getPropertyValue("--tilt"));
      expect(Math.abs(tilt)).toBeLessThanOrEqual(3);
    }
  });

  it("doesn't tilt notes in quiet mode", async () => {
    localStorage.setItem("price-diaries:mode", "quiet");
    renderNotes(NOTES);
    const items = await screen.findAllByRole("listitem");
    expect(items.every((item) => item.style.getPropertyValue("--tilt") === "")).toBe(true);
  });
});
