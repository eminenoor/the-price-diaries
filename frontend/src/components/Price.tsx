import { formatPrice } from "../format";

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

/** "Card price, regular 950,00" under a member price; nothing otherwise. */
export function RegularPriceNote({ regular }: { regular: number | null }) {
  if (regular === null) return null;
  return (
    <span className="regular-note">
      Card price. Regular <Price value={regular} />
    </span>
  );
}
