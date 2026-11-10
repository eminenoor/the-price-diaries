import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Price } from "./components/Price";
import { PRODUCTS, renderIndex } from "./pages/IndexPage.test";

describe("accessibility", () => {
  it("reads prices as words, not as the styled pieces", () => {
    render(<Price value={1299.9} />);
    expect(screen.getByText("1.299,90 lira")).toBeInTheDocument();
    expect(screen.getByText("1.299,90 lira").closest(".price")).not.toHaveAttribute("aria-label");
  });

  it("lists windows in logical order, whatever the scatter: floor, room, then name", async () => {
    renderIndex(PRODUCTS);
    const skincare = await screen.findByRole("region", { name: "skincare" });
    const names = within(skincare)
      .getAllByRole("link")
      .map((a) => a.textContent ?? "");
    expect(names[0]).toMatch(/^Barrier cream/); // room "Moisturizers"
    expect(names[1]).toMatch(/^Aloe toner/); // room "Toners", A before Z
    expect(names[2]).toMatch(/^Zinc toner/);
  });

  it("states every window's status in words", async () => {
    renderIndex(PRODUCTS);
    const deal = await screen.findByRole("link", { name: /Zinc toner/ });
    expect(deal).toHaveTextContent("lowest ever");
    expect(deal).toHaveTextContent("300,00 lira");
    expect(screen.getByRole("link", { name: /Aloe toner/ })).toHaveTextContent("no change");
    expect(screen.getByRole("link", { name: /Coffee/ })).toHaveTextContent("not checked yet");
  });

  it("keeps the window drawing out of the accessibility tree", async () => {
    renderIndex(PRODUCTS);
    const link = await screen.findByRole("link", { name: /Zinc toner/ });
    expect(link.querySelector(".window")).toHaveAttribute("aria-hidden", "true");
  });
});
