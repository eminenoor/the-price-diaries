// Types mirror backend/src/price_diaries/schemas.py.

export interface Store {
  key: string;
  name: string;
  domains: string[];
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

export interface Product {
  id: number;
  url: string;
  name: string;
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
  sparkline: number[];
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

export interface ProductDetail extends Product {
  history: PricePoint[];
  anomalies: Anomaly[];
}

export interface CheckResult {
  product_id: number;
  ok: boolean;
  price: number | null;
  error: string | null;
}

export interface NewProduct {
  url: string;
  name: string;
  category_id?: number;
  target_price?: number;
}

/** Fields that can be changed later. brand "" removes it, so checks won't fill it in. */
export interface ProductChanges extends Partial<NewProduct> {
  brand?: string;
}

export class ApiError extends Error {
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
  stores: () => request<Store[]>("/stores"),
  categories: () => request<Category[]>("/categories"),
  createCategory: (body: NewCategory) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: number, body: Partial<Pick<Category, "name" | "color">>) =>
    request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  removeCategory: (id: number) => request<void>(`/categories/${id}`, { method: "DELETE" }),
  products: () => request<Product[]>("/products"),
  product: (id: number) => request<ProductDetail>(`/products/${id}`),
  create: (body: NewProduct) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: ProductChanges) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => request<void>(`/products/${id}`, { method: "DELETE" }),
  check: (id: number) => request<CheckResult>(`/products/${id}/check`, { method: "POST" }),
  checkAll: () => request<CheckResult[]>("/check", { method: "POST" }),
};
