import { formatPrice } from "../format";

interface PriceProps {
  value: number;
  size?: "hero" | "large" | "row";
  className?: string;
}

/**
 * Prices set like a printed shelf tag: lira in a Didone face, kuruş raised
 * and smaller. This is the design's signature element.
 */
export function Price({ value, size = "row", className = "" }: PriceProps) {
  const [lira, kurus] = formatPrice(value).split(",");
  return (
    <span className={`price price--${size} ${className}`} aria-label={`${formatPrice(value)} lira`}>
      <span className="price__currency" aria-hidden="true">
        ₺
      </span>
      <span aria-hidden="true">{lira}</span>
      <sup className="price__kurus" aria-hidden="true">
        {kurus}
      </sup>
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
