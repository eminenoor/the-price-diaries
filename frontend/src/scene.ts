/**
 * Pure logic behind the "after dark" design: what state each window is in,
 * where it hangs, which floor it belongs to and what the subtitle says.
 * No React here, so all of it is unit-tested in scene.test.ts.
 */
import type { Category, Product } from "./api";
import { formatChange, pickFeature } from "./format";

// --- window state -------------------------------------------------------------

export type WindowKind = "deal" | "fake" | "steady" | "up" | "blocked" | "waiting" | "error";

export interface WindowState {
  kind: WindowKind;
  /** Status in plain words. Always shown, so colour never carries meaning alone. */
  words: string;
}

export function windowState(product: Product, storeName: string): WindowState {
  const s = product.summary;
  if (product.blocked) return { kind: "blocked", words: `${storeName} doesn't allow automated checks` };
  if (product.last_error) return { kind: "error", words: "last check failed" };
  if (!s) return { kind: "waiting", words: "not checked yet" };
  if (s.fake_sale) return { kind: "fake", words: "fake sale" };

  const dropped = s.change_pct !== null && s.change_pct < 0;
  if (dropped && s.is_all_time_low) return { kind: "deal", words: "lowest ever" };
  if (product.target_price !== null && s.current <= product.target_price)
    return { kind: "deal", words: "below your alert price" };
  if (dropped && s.current <= s.lowest_30d) return { kind: "deal", words: "lowest in 30 days" };
  if (dropped) return { kind: "deal", words: `down ${formatChange(s.change_pct!).slice(1)}` };
  if (s.change_pct !== null && s.change_pct > 0)
    return { kind: "up", words: `up ${formatChange(s.change_pct).slice(1)}` };
  return { kind: "steady", words: "no change" };
}

/** Lights on: the window is worth looking at. Dark: nothing to see tonight. */
export function isLit(kind: WindowKind): boolean {
  return kind === "deal" || kind === "fake";
}

// --- the subtitle ---------------------------------------------------------------

/** One film-subtitle sentence with the most important news on the page. */
export function newsLine(products: Product[], storeName: (key: string) => string): string {
  if (products.length === 0) return "No lights on yet. Pin a new window to start tracking a price.";

  const states = products.map((p) => ({ p, state: windowState(p, storeName(p.store)) }));
  const fakes = states.filter((x) => x.state.kind === "fake");
  const deals = states.filter((x) => x.state.kind === "deal");
  const feature = pickFeature(deals.map((x) => x.p));
  const best = deals.find((x) => x.p.id === feature?.id);

  const dealClause = best
    ? best.state.words === "lowest ever"
      ? `${best.p.name} is the lowest it's ever been at ${storeName(best.p.store)}`
      : `${best.p.name} is ${best.state.words} at ${storeName(best.p.store)}`
    : null;

  if (dealClause && fakes.length > 0) {
    const count = fakes.length === 1 ? "one sale" : `${fakes.length} sales`;
    return `${dealClause}, but ${count} tonight ${fakes.length === 1 ? "is" : "are"} fake.`;
  }
  if (dealClause) return `${dealClause}.`;
  if (fakes.length === 1) {
    const { p } = fakes[0];
    return `The sale on ${p.name} at ${storeName(p.store)} is fake: the price went up first.`;
  }
  if (fakes.length > 1) return `${fakes.length} sales tonight are fake: the prices went up first.`;
  return "A quiet night. Nothing on your list got cheaper.";
}

// --- scatter ----------------------------------------------------------------------

export interface Placement {
  /** Degrees, between -3 and 3. */
  rotate: number;
  /** Width as a share of the column, 0.78 to 1. */
  size: number;
  /** Sideways nudge as a share of the free space, -1 (left) to 1 (right). */
  nudge: number;
  /** Drop from the top of the row in px (scaled down on small screens). */
  drop: number;
  /** Tape angle on the labels, -8 to 8 degrees. */
  tape: number;
}

/** FNV-1a: a small, stable string hash. */
function hash(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Mulberry32: turns one seed into a stream of numbers in [0, 1). */
function random(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (n: number, places = 2) => Math.round(n * 10 ** places) / 10 ** places;

/** Where a window hangs. The same id always gives the same placement. */
export function placement(id: number): Placement {
  const next = random(hash(`window:${id}`));
  return {
    rotate: round(next() * 6 - 3, 1),
    size: round(0.78 + next() * 0.22),
    nudge: round(next() * 2 - 1),
    drop: Math.round(next() * 56),
    tape: Math.round(next() * 16 - 8),
  };
}

// --- floors -----------------------------------------------------------------------

export interface Floor {
  /** null for products that have no floor yet. */
  floor: Category | null;
  products: Product[];
}

/** Floors in their saved order, each with its products (by room, then name). */
export function floorsOf(categories: Category[], products: Product[]): Floor[] {
  const byId = new Map(categories.map((c) => [c.id, c]));
  const floorOf = (p: Product): Category | null => {
    const category = p.category_id === null ? undefined : byId.get(p.category_id);
    if (!category) return null;
    return category.parent_id === null ? category : (byId.get(category.parent_id) ?? null);
  };
  const roomName = (p: Product) => {
    const c = p.category_id === null ? undefined : byId.get(p.category_id);
    return c && c.parent_id !== null ? c.name : "";
  };
  const sorted = [...products].sort(
    (a, b) => roomName(a).localeCompare(roomName(b)) || a.name.localeCompare(b.name),
  );

  const floors: Floor[] = categories
    .filter((c) => c.parent_id === null)
    .map((floor) => ({ floor, products: sorted.filter((p) => floorOf(p)?.id === floor.id) }));
  const homeless = sorted.filter((p) => floorOf(p) === null);
  if (homeless.length) floors.push({ floor: null, products: homeless });
  return floors;
}

export function roomOf(categories: Category[], product: Product): Category | undefined {
  const c = categories.find((x) => x.id === product.category_id);
  return c && c.parent_id !== null ? c : undefined;
}

// --- colour -----------------------------------------------------------------------

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two "#RRGGBB" colours, 1 to 21. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

export const INK = "#141414";
export const WHITE = "#FFFFFF";

/** Text colour for a label printed on a user-chosen floor colour. */
export function inkOn(background: string): string {
  return contrast(background, INK) >= contrast(background, WHITE) ? INK : WHITE;
}
