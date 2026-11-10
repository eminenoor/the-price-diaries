import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PricePoint } from "../api";
import { LinerNotes, usualRegular } from "./LinerNotes";

const point = (day: number, price: number, member_price: number | null): PricePoint => ({
  checked_at: new Date(2026, 10, day, 9, 17).toISOString(),
  price,
  member_price,
  currency: "TRY",
  in_stock: true,
});

describe("LinerNotes", () => {
  it("writes the card-price note once, in the header", () => {
    const history = [point(1, 950, 494), point(2, 950, 494), point(3, 950, 480)];
    const { container } = render(<LinerNotes history={history} anomalies={[]} />);
    expect(container.querySelector(".sleeve__card")).toHaveTextContent("Card prices, regular 950,00 lira");
    expect(screen.queryByText(/card price, regular/i)).not.toBeInTheDocument();
    for (const track of container.querySelectorAll(".track"))
      expect(track).not.toHaveTextContent("950,00");
  });

  it("notes a regular price only on the rows where it was different", () => {
    const history = [point(1, 950, 494), point(2, 1158.29, 602.31), point(3, 950, 494)];
    const { container } = render(<LinerNotes history={history} anomalies={[]} />);
    const tracks = [...container.querySelectorAll(".track")];
    expect(tracks[1]).toHaveTextContent("regular 1.158,29 lira");
    expect(tracks[0]).not.toHaveTextContent("regular");
  });

  it("has no card-price note without card prices", () => {
    const { container } = render(
      <LinerNotes history={[point(1, 300, null), point(2, 310, null)]} anomalies={[]} />,
    );
    expect(container.querySelector(".sleeve__card")).toBeNull();
    expect(usualRegular([point(1, 300, null)])).toBeNull();
  });
});
