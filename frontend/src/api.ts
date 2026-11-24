// Types mirror backend/src/price_diaries/schemas.py.

/** How the app runs. set_date: the day PD_TODAY sets (the demo), as "2026-12-01". */
export interface AppInfo {
  set_date: string | null;
}

export interface Store {
  key: string;
  name: string;
}

/** A floor (parent_id null, e.g. Skincare) or a room on a floor (e.g. Toners). */
export interface Category {
  id: number;
  name: string;
  parent_id: number | null;
  /** "#RRGGBB" */
  color: string;
}

export interface NewCategory {
  name: string;
  parent_id?: number;
  color?: string;
}

export interface Summary {
  current: number;
  previous: number | null;
  lowest: number;
  lowest_at: string;
  highest: number;
  highest_at: string;
  lowest_30d: number;
  change_pct: number | null;
  is_all_time_low: boolean;
  fake_sale: boolean;
}

/** Millilitres, grams or pieces. */
export type SizeUnit = "ml" | "g" | "pcs";

/** A product's pack size, normalised: 1,5 L is { amount: 1500, unit: "ml" }. */
export interface Size {
  amount: number;
  unit: SizeUnit;
  /** Read from the product's name, the store page, or set by the user. */
  source: "name" | "page" | "user";
}

/** The current price (the card price when shown) for `per` of `unit`: ₺2,53 / 10 ml. */
export interface UnitPrice {
  price: number;
  per: number;
  unit: SizeUnit;
}

/** The same product is cheaper at another store today, for this product's size. */
export interface ElsewhereNote {
  product_id: number;
  store: string;
  store_name: string;
  saving: number;
}

/** The same product at another store. */
export interface Offer {
  product_id: number;
  name: string;
  store: string;
  store_name: string;
  /** The price you'd pay there (the card price when shown). */
  price: number;
  unit_price: UnitPrice | null;
  checked_at: string;
  in_stock: boolean;
  /** How much less it costs there than here, for this size; negative when it costs more. */
  saving: number | null;
}

export interface Product {
  id: number;
  url: string;
  /** The name to show: the user's, or the most complete store name in its group. */
  name: string;
  /** This store's own name for it. */
  listing_name: string;
  /** From the store page, or set by the user; null if unknown. */
  brand: string | null;
  store: string;
  /** A room (or a floor). See Category. */
  category_id: number | null;
  target_price: number | null;
  /** Product photo from the store page (https), or null. */
  image_url: string | null;
  last_error: string | null;
  /** The store refuses automated checks (blinds down). */
  blocked: boolean;
  created_at: string;
  summary: Summary | null;
  /** Latest shelf price, set only when the main price shown is a member price. */
  regular_price: number | null;
  /** Pack size, or null if unknown. */
  size: Size | null;
  /** Null without a size or a price. */
  unit_price: UnitPrice | null;
  /** Barcode, 14 digits, or null. */
  gtin: string | null;
  /** Null unless another store is cheaper today. */
  cheaper_elsewhere: ElsewhereNote | null;
}

export interface PricePoint {
  checked_at: string;
  price: number;
  member_price: number | null;
  currency: string;
  in_stock: boolean;
}

export interface Anomaly {
  checked_at: string;
  price: number;
  change_pct: number;
  score: number;
}

/** Waiting for the shown times on past days: how often it paid less, and by how much. */
export interface Backtest {
  trials: number;
  wins: number;
  average_saving_pct: number;
}

export interface SaleCycle {
  every_days: number;
  typical_pct: number;
  last_days_ago: number;
}

export interface YearlyEvent {
  name: "11.11" | "Efsane Cuma";
  /** Off the usual price, the last time. */
  pct: number;
}

/** When this product has been cheapest. Only patterns that would have helped are given. */
export interface BestTime {
  enough_history: boolean;
  days_of_month: number[];
  /** Monday is 0. */
  weekdays: number[];
  sale_cycle: SaleCycle | null;
  events: YearlyEvent[];
  backtest: Backtest | null;
}

export interface ProductDetail extends Product {
  history: PricePoint[];
  anomalies: Anomaly[];
  /** The same product at other stores, cheapest first. */
  elsewhere: Offer[];
  /** Every other product in its group, checked or not, by id. */
  linked_ids: number[];
  best_time: BestTime;
}

export interface CheckResult {
  product_id: number;
  ok: boolean;
  price: number | null;
  error: string | null;
}

export type NoteKind = "target" | "lowest" | "fake_sale" | "cheaper" | "back_in_stock" | "sunday_paper";

/** A note in the inbox: about one product, or the Sunday paper (no product). */
export interface Note {
  id: number;
  kind: NoteKind;
  product_id: number | null;
  product_name: string | null;
  store: string | null;
  store_name: string | null;
  /** The price at the check before; for "cheaper", the price here. */
  old_price: number | null;
  /** The new price; for "cheaper", the other store's price for this size. */
  new_price: number | null;
  /** For "cheaper": the store that sells it. */
  other_store_name: string | null;
  /** For "sunday_paper": the Monday of the week it's about, "2026-11-09". */
  week: string | null;
  created_at: string;
  read: boolean;
}

export interface Notes {
  unread: number;
  /** The latest notes, newest first. */
  notes: Note[];
}

/** One product in the Sunday paper. */
export interface PaperItem {
  product_id: number;
  name: string;
  store_name: string;
}

/** The price before the week against the last price in it. */
export interface PaperMove extends PaperItem {
  old_price: number;
  new_price: number;
  change_pct: number;
}

export interface PaperLow extends PaperItem {
  /** The week's lowest price. */
  price: number;
  at: string;
  /** The lowest price before the week. */
  previous_low: number;
}

export interface PaperFakeSale extends PaperItem {
  /** The "sale" price. */
  price: number;
  /** The raised price before it. */
  peak: number;
  at: string;
}

export interface PaperCheaper extends PaperItem {
  other_store_name: string;
  price_here: number;
  /** The other store's price for this product's size. */
  price_there: number;
  at: string;
}

export interface PaperTrouble extends PaperItem {
  /** Checks that couldn't get a price this week. */
  failed_checks: number;
  last_error: string | null;
  /** When it went out of stock this week. */
  out_of_stock_at: string | null;
}

/** One week, Monday to Sunday. Every list may be empty. */
export interface Paper {
  week_start: string;
  week_end: string;
  /** null before the first check. */
  previous_week: string | null;
  /** null when the next paper isn't out yet. */
  next_week: string | null;
  /** Products checked at least once this week. */
  products_checked: number;
  /** Biggest drop first. */
  drops: PaperMove[];
  new_lows: PaperLow[];
  fake_sales: PaperFakeSale[];
  /** Biggest saving first. */
  cheaper: PaperCheaper[];
  /** Biggest rise first. */
  rises: PaperMove[];
  /** Failed checks or out of stock. */
  trouble: PaperTrouble[];
}

export interface NewProduct {
  url: string;
  name: string;
  category_id?: number;
  target_price?: number;
}

/** Fields that can be changed later. */
export interface ProductChanges extends Partial<NewProduct> {
  brand?: string;
  /** As written on the pack: "150 ml", "1,5 L". "" removes it, so checks won't fill it in. */
  size?: string;
  /** Shown at every store in the group. "" goes back to the most complete store name. */
  display_name?: string;
}

class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  app: () => request<AppInfo>("/app"),
  stores: () => request<Store[]>("/stores"),
  categories: () => request<Category[]>("/categories"),
  createCategory: (body: NewCategory) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  products: () => request<Product[]>("/products"),
  product: (id: number) => request<ProductDetail>(`/products/${id}`),
  create: (body: NewProduct) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: ProductChanges) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => request<void>(`/products/${id}`, { method: "DELETE" }),
  link: (id: number, otherId: number) =>
    request<ProductDetail>(`/products/${id}/link`, {
      method: "POST",
      body: JSON.stringify({ other_id: otherId }),
    }),
  unlink: (id: number) => request<void>(`/products/${id}/link`, { method: "DELETE" }),
  check: (id: number) => request<CheckResult>(`/products/${id}/check`, { method: "POST" }),
  checkAll: () => request<CheckResult[]>("/check", { method: "POST" }),
  notes: () => request<Notes>("/notifications"),
  readNote: (id: number) => request<void>(`/notifications/${id}/read`, { method: "POST" }),
  readAllNotes: () => request<void>("/notifications/read", { method: "POST" }),
  /** The paper for the week a date falls in; without one, the latest paper. */
  paper: (week: string | null) =>
    request<Paper>(week ? `/paper?week=${encodeURIComponent(week)}` : "/paper"),
};
