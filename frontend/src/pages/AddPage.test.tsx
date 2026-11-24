import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddPage } from "./AddPage";

const CATEGORIES = [
  { id: 1, name: "Skincare", parent_id: null, color: "#E8B4B8" },
  { id: 5, name: "Toners", parent_id: 1, color: "#E8B4B8" },
  { id: 2, name: "Pantry", parent_id: null, color: "#C9D6A3" },
];

function mockApi() {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace("/api", "");
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const json = (data: unknown, status = 200) =>
      new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
    if (path === "/stores") return json([{ key: "gratis", name: "Gratis" }]);
    if (path === "/categories" && method === "GET") return json(CATEGORIES);
    if (path === "/categories" && method === "POST")
      return json({ id: 9, color: "#E8B4B8", parent_id: null, ...(body as object) }, 201);
    if (path === "/products" && method === "POST") return json({ id: 42 }, 201);
    if (path === "/products/42/check") return json({ product_id: 42, ok: true, price: 1, error: null });
    return json({ detail: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/add"]}>
        <Routes>
          <Route path="/add" element={<AddPage />} />
          <Route path="/products/:id" element={<p>product page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("AddPage", () => {
  it("creates a new room, tracks the product in it, checks it and opens it", async () => {
    const calls = mockApi();
    renderPage();

    fireEvent.change(screen.getByLabelText("Product link"), {
      target: { value: "https://www.gratis.com/tonik-p-1" },
    });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Toner" } });
    fireEvent.click(await screen.findByLabelText("skincare"));
    fireEvent.change(screen.getByLabelText("Room"), { target: { value: "Exfoliating toners" } });
    fireEvent.change(screen.getByLabelText("Alert me at"), { target: { value: "249,90" } });
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));

    expect(await screen.findByText("product page")).toBeInTheDocument();
    const writes = calls.filter((c) => c.method === "POST");
    expect(writes).toEqual([
      { method: "POST", path: "/categories", body: { name: "Exfoliating toners", parent_id: 1 } },
      {
        method: "POST",
        path: "/products",
        body: { url: "https://www.gratis.com/tonik-p-1", name: "Toner", category_id: 9, target_price: 249.9 },
      },
      { method: "POST", path: "/products/42/check", body: undefined },
    ]);
  });

  it("reuses an existing room, ignoring case", async () => {
    const calls = mockApi();
    renderPage();
    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: "https://www.gratis.com/x" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Toner" } });
    fireEvent.click(await screen.findByLabelText("skincare"));
    fireEvent.change(screen.getByLabelText("Room"), { target: { value: "toners" } });
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));

    await screen.findByText("product page");
    expect(calls.find((c) => c.path === "/categories" && c.method === "POST")).toBeUndefined();
    expect(calls.find((c) => c.path === "/products")?.body).toMatchObject({ category_id: 5 });
  });

  it("explains what's missing instead of submitting", async () => {
    const calls = mockApi();
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Add both the product link and a name you'll recognise.",
    );
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(false));
  });
});
