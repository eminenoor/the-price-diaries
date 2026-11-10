// Types mirror backend/src/price_diaries/schemas.py.

export interface Store {
  key: string;
  name: string;
  domains: string[];
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
  store: string;
  category: string | null;
  target_price: number | null;
  last_error: string | null;
  created_at: string;
  summary: Summary | null;
  sparkline: number[];
}

export interface PricePoint {
  checked_at: string;
  price: number;
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
  category?: string;
  target_price?: number;
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
  products: () => request<Product[]>("/products"),
  product: (id: number) => request<ProductDetail>(`/products/${id}`),
  create: (body: NewProduct) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: Partial<NewProduct>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => request<void>(`/products/${id}`, { method: "DELETE" }),
  check: (id: number) => request<CheckResult>(`/products/${id}/check`, { method: "POST" }),
  checkAll: () => request<CheckResult[]>("/check", { method: "POST" }),
};
