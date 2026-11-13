import type { UnitPrice as UnitPriceData } from "../api";
import { formatBasis, formatPrice } from "../format";

interface PriceProps {
  value: number;
  size?: "hero" | "large" | "row";
  className?: string;
}

/**
 * Prices in Bricolage Grotesque 800, set tight like a film-poster credit:
 * a small lira sign, the lira amount, and the kuruş raised and smaller.
 */
export function Price({ value, size = "row", className = "" }: PriceProps) {
  const [lira, kurus] = formatPrice(value).split(",");
  return (
    <span className={`price price--${size} ${className}`}>
      {/* aria-label isn't allowed on a plain span, so screen readers get real text. */}
      <span className="visually-hidden">{formatPrice(value)} lira</span>
      <span className="price__currency" aria-hidden="true">
        ₺
      </span>
      <span aria-hidden="true">{lira}</span>
      <span className="price__kurus" aria-hidden="true">
        ,{kurus}
      </span>
    </span>
  );
}

/**
 * "₺2,53 / 10 ml" under a price, so different pack sizes compare. Screen readers
 * hear "2,53 lira per 10 ml". Nothing when the size or the price is unknown.
 */
export function UnitPrice({ unit, className = "" }: { unit: UnitPriceData | null; className?: string }) {
  if (unit === null) return null;
  return (
    <span className={`unit-price ${className}`}>
      <Price value={unit.price} />
      <span aria-hidden="true"> / </span>
      <span className="visually-hidden"> per </span>
      {formatBasis(unit.per, unit.unit)}
    </span>
  );
}

/** "Card price, regular 950,00" under a member price; nothing otherwise. */
export function RegularPriceNote({ regular }: { regular: number | null }) {
  if (regular === null) return null;
  return (
    <span className="regular-note">
      Card price. Regular <Price value={regular} />
    </span>
  );
}
