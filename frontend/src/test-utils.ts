import { expect } from "vitest";

/** A unit price is seen as "₺25,30 / 10 ml" and heard as "25,30 lira per 10 ml". */
export function expectUnitPrice(element: Element | null, price: string, basis: string) {
  expect(element).not.toBeNull();
  const hidden = [...element!.querySelectorAll("[aria-hidden='true']")];
  const seen = hidden.map((e) => e.textContent).join("") + element!.lastChild?.textContent;
  expect(seen).toBe(`₺${price} / ${basis}`);
  expect(element).toHaveTextContent(`${price} lira`);
  expect(element!.querySelector(":scope > .visually-hidden")).toHaveTextContent("per");
}
