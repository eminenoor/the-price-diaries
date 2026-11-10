import type { Product, Summary } from "./api";

const lira = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 1299.9 -> "1.299,90" (Turkish grouping, the way stores print prices). */
export function formatPrice(value: number): string {
  return lira.format(value);
}

const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

export function formatDate(iso: string): string {
  return shortDate.format(new Date(iso));
}

export function formatChange(pct: number): string {
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

/**
 * One plain sentence about what matters most right now.
 * Ordered by how useful it is to someone deciding whether to buy.
 */
export function insight(product: Product): string {
  const s: Summary | null = product.summary;
  if (product.last_error) return `Last check failed: ${product.last_error}`;
  if (!s) return "Waiting for the first price check.";

  if (s.fake_sale)
    return "This discount follows a recent price rise, so it isn't really cheaper than before.";
  if (product.target_price !== null && s.current <= product.target_price)
    return `Below your alert price of ${formatPrice(product.target_price)}. A good time to buy.`;
  if (s.is_all_time_low && s.previous !== null) return "The lowest price since you started tracking.";
  if (s.current <= s.lowest_30d) return "The lowest price in the last 30 days.";
  if (s.change_pct !== null && s.change_pct > 0)
    return `Up ${formatChange(s.change_pct).slice(1)} since the last check. Lowest was ${formatPrice(s.lowest)} on ${formatDate(s.lowest_at)}.`;
  if (s.change_pct !== null && s.change_pct < 0)
    return `Down ${formatChange(s.change_pct).slice(1)} since the last check.`;
  return `No change. Lowest was ${formatPrice(s.lowest)} on ${formatDate(s.lowest_at)}.`;
}

/** Which product deserves the top of the page: the best real deal right now. */
export function pickFeature(products: Product[]): Product | undefined {
  const score = (p: Product) => {
    const s = p.summary;
    if (!s || s.fake_sale || p.last_error) return -Infinity;
    const vsHigh = (s.highest - s.current) / s.highest; // how far below its peak
    return vsHigh + (s.is_all_time_low ? 1 : 0) + (s.current <= s.lowest_30d ? 0.5 : 0);
  };
  return [...products].sort((a, b) => score(b) - score(a))[0];
}
