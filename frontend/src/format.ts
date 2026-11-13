import type { Product, Size, SizeUnit, Summary } from "./api";

const lira = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 1299.9 -> "1.299,90" (Turkish grouping, the way stores print prices). */
export function formatPrice(value: number): string {
  return lira.format(value);
}

const sizeNumber = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 });

/** What a unit price is quoted for: "10 ml", "100 g", "piece". */
export function formatBasis(per: number, unit: SizeUnit): string {
  if (unit === "pcs") return per === 1 ? "piece" : `${per} pieces`;
  return `${per} ${unit}`;
}

/** A pack size the way a pack prints it: "150 ml", "1,5 L", "2,5 kg", "60 pieces". */
export function formatSize({ amount, unit }: Pick<Size, "amount" | "unit">): string {
  if (unit === "pcs") return amount === 1 ? "1 piece" : `${sizeNumber.format(amount)} pieces`;
  if (amount >= 1000) return `${sizeNumber.format(amount / 1000)} ${unit === "ml" ? "L" : "kg"}`;
  return `${sizeNumber.format(amount)} ${unit}`;
}

const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

export function formatDate(iso: string): string {
  return shortDate.format(new Date(iso));
}

const clock = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });

/** 09:17 */
export function formatTime(date: Date): string {
  return clock.format(date);
}

/** One check, as the chart tooltip shows it: "10 Nov, 09:17 · ₺268,22". */
export function formatCheck(date: Date, price: number): string {
  return `${shortDate.format(date)}, ${formatTime(date)} · ₺${formatPrice(price)}`;
}

export function formatChange(pct: number): string {
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

function isToday(iso: string, now: Date): boolean {
  return new Date(iso).toDateString() === now.toDateString();
}

/**
 * One plain sentence about what matters most right now.
 * Ordered by how useful it is to someone deciding whether to buy.
 */
export function insight(product: Product, now: Date = new Date()): string {
  const s: Summary | null = product.summary;
  if (product.last_error) return `Last check failed: ${product.last_error}`;
  if (!s) return "Waiting for the first price check.";

  if (s.fake_sale)
    return "This discount follows a recent price rise, so it isn't really cheaper than before.";
  if (product.target_price !== null && s.current <= product.target_price)
    return `Below your alert price of ${formatPrice(product.target_price)}. A good time to buy.`;
  if (s.previous === null)
    return isToday(s.lowest_at, now)
      ? "First check today. Come back tomorrow to see if it moves."
      : `First check on ${formatDate(s.lowest_at)}. The next check shows if it moves.`;
  if (s.is_all_time_low && s.current < s.highest) return "The lowest price since you started tracking.";
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
