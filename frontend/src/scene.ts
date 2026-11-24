/**
 * Pure logic behind the "after dark" design: what state each window is in,
 * where it hangs, which floor it belongs to and what the subtitle says.
 * No React here, so all of it is unit-tested in scene.test.ts.
 */
import type { Backtest, BestTime, Category, NoteKind, Paper, PaperMove, Product, Summary } from "./api";
import { formatChange, formatDate, formatPrice, parseDay, pickFeature } from "./format";

// --- window state -------------------------------------------------------------

export type WindowKind =
  | "deal"
  | "fake"
  | "steady"
  | "up"
  | "first"
  | "blocked"
  | "waiting"
  | "error";

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

  // One check: nothing to compare with yet, so no "no change" and no "lowest in 30 days".
  const first = s.previous === null;
  if (first && product.target_price !== null && s.current <= product.target_price)
    return { kind: "deal", words: "below your alert price" };
  if (first) return { kind: "first", words: "first check" };

  const dropped = s.change_pct !== null && s.change_pct < 0;
  // Stays lit while the price sits at its all-time low, even with no change since
  // the last check. A price that has never moved isn't a low, so it stays dark.
  if (s.is_all_time_low && s.current < s.highest) return { kind: "deal", words: "lowest ever" };
  // Below the alert price stays lit too, changed or not.
  if (product.target_price !== null && s.current <= product.target_price)
    return { kind: "deal", words: "below your alert price" };
  if (dropped && s.current <= s.lowest_30d) return { kind: "deal", words: "lowest in 30 days" };
  if (dropped) return { kind: "deal", words: `down ${formatChange(s.change_pct!).slice(1)}` };
  if (s.change_pct !== null && s.change_pct > 0)
    return { kind: "up", words: `up ${formatChange(s.change_pct).slice(1)}` };
  return { kind: "steady", words: "no change" };
}

export interface Lighting {
  light: "lamp" | "rose" | "dark";
  curtains: "open" | "half" | "closed";
  blinds: boolean;
}

/**
 * How a window looks for each status, everywhere a window is drawn: warm light
 * and open curtains only for a good deal, rose-red light for a fake sale, and
 * dark with the curtains closed when there's no news (no change, price up, one
 * check, not checked, failed). A store that blocks checks has its blinds down.
 */
export function lighting(kind: WindowKind): Lighting {
  if (kind === "deal") return { light: "lamp", curtains: "open", blinds: false };
  if (kind === "fake") return { light: "rose", curtains: "half", blinds: false };
  return { light: "dark", curtains: "closed", blinds: kind === "blocked" };
}

// --- pencil notes on the chart ------------------------------------------------------

export interface PencilNote {
  kind: "lowest" | "highest" | "low30" | "alert";
  /** Handwritten, short: "lowest ₺378,89 on 11 Nov". */
  text: string;
  /** The point the note is about (for the alert, the line's height). */
  date: Date | null;
  price: number;
}

/**
 * The handwritten notes pinned on the chart instead of stat boxes: an arrow to
 * the lowest point, the highest and the 30-day low when they say something
 * new, and the alert price written on its dashed line.
 */
export function pencilNotes(
  history: { checked_at: string; price: number; member_price: number | null }[],
  summary: Summary,
  target: number | null,
): PencilNote[] {
  const points = history.map((p) => ({ date: new Date(p.checked_at), price: p.member_price ?? p.price }));
  if (points.length === 0) return [];
  const notes: PencilNote[] = [];
  const latest = (price: number) => [...points].reverse().find((p) => p.price === price);

  const low = points.reduce((a, b) => (b.price <= a.price ? b : a));
  notes.push({
    kind: "lowest",
    text: `lowest ₺${formatPrice(low.price)} on ${formatDate(low.date.toISOString())}`,
    ...low,
  });

  // The highest and the 30-day low only when they are new numbers, not the current
  // price, the lowest or each other.
  const seen = [summary.current, summary.lowest, low.price];
  const high = latest(summary.highest);
  if (high && !seen.includes(summary.highest))
    notes.push({ kind: "highest", text: `highest ₺${formatPrice(high.price)}`, ...high });
  seen.push(summary.highest);

  const low30 = latest(summary.lowest_30d);
  if (low30 && !seen.includes(summary.lowest_30d))
    notes.push({ kind: "low30", text: `30-day low ₺${formatPrice(low30.price)}`, ...low30 });

  if (target !== null)
    notes.push({ kind: "alert", text: `alert ₺${formatPrice(target)}`, date: null, price: target });
  return notes;
}

// --- placing the pencil notes -------------------------------------------------------

export interface Point {
  x: number;
  y: number;
}

/** A rectangle in px, from its top-left corner. */
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface NoteToPlace {
  kind: PencilNote["kind"];
  text: string;
  /** The point the note describes, in px. null for the alert (it goes on its line). */
  at: Point | null;
}

export interface NoteScene {
  notes: NoteToPlace[];
  /** Every check in px, oldest first. The line steps between them (step-after). */
  line: Point[];
  /** Every dot and ring drawn on the chart, in px. */
  dots: (Point & { r: number })[];
  /** The gold dot (lowest point) in px, which the arrow points at. */
  lowest: Point & { r: number };
  /** Height of the dashed alert line in px, or null. */
  alertY: number | null;
  /** The plot area in px; notes stay inside it. */
  frame: { left: number; right: number; top: number; bottom: number };
  measure: (text: string) => { w: number; h: number };
}

export interface PlacedNote {
  kind: PencilNote["kind"];
  text: string;
  box: Box;
}

export type NoteLayout =
  | { fits: true; notes: PlacedNote[]; arrow: { from: Point; to: Point } }
  | { fits: false };

/** Room kept clear around the line, dots and other notes, in px. */
const CLEARANCE = 4;
/**
 * The arrow from the "lowest" note to the gold dot: long enough to read as an
 * arrow, short enough that the note stays near the dot. In px, note to dot centre.
 */
const ARROW_MIN = 34;
const NEAR = 90;

const grow = (b: Box, by: number): Box => ({
  x: b.x - by,
  y: b.y - by,
  w: b.w + 2 * by,
  h: b.h + 2 * by,
});

export function boxesOverlap(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** Does the segment from p to q pass through the box? (Liang–Barsky clipping.) */
export function segmentHitsBox(p: Point, q: Point, b: Box): boolean {
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  let t0 = 0;
  let t1 = 1;
  const edges: [number, number][] = [
    [-dx, p.x - b.x],
    [dx, b.x + b.w - p.x],
    [-dy, p.y - b.y],
    [dy, b.y + b.h - p.y],
  ];
  for (const [step, room] of edges) {
    if (step === 0) {
      if (room < 0) return false;
      continue;
    }
    const t = room / step;
    if (step < 0) t0 = Math.max(t0, t);
    else t1 = Math.min(t1, t);
    if (t0 > t1) return false;
  }
  return true;
}

/** Do segments a–b and c–d cross? */
function crosses(a: Point, b: Point, c: Point, d: Point): boolean {
  const side = (p: Point, q: Point, r: Point) =>
    Math.sign((q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x));
  return side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0;
}

/** The point on a box's edge closest to p (p is outside the box). */
function nearestOnEdge(b: Box, p: Point): Point {
  return {
    x: Math.min(Math.max(p.x, b.x), b.x + b.w),
    y: Math.min(Math.max(p.y, b.y), b.y + b.h),
  };
}

/** The step line as segments: across at each price, then down or up to the next. */
export function stepSegments(line: Point[]): [Point, Point][] {
  const segments: [Point, Point][] = [];
  for (let i = 0; i + 1 < line.length; i++) {
    const corner = { x: line[i + 1].x, y: line[i].y };
    segments.push([line[i], corner], [corner, line[i + 1]]);
  }
  return segments;
}

type Direction =
  | "above"
  | "below"
  | "left"
  | "right"
  | "aboveLeft"
  | "aboveRight"
  | "belowLeft"
  | "belowRight";

const PREFERENCE: Record<"lowest" | "highest" | "low30", Direction[]> = {
  lowest: ["below", "belowLeft", "belowRight", "left", "right", "aboveLeft", "aboveRight", "above"],
  highest: ["above", "aboveLeft", "aboveRight", "right", "left", "belowLeft", "belowRight", "below"],
  low30: ["below", "above", "belowLeft", "belowRight", "aboveLeft", "aboveRight", "right", "left"],
};

/** Boxes next to a point, nearest first, in order of preference. */
function spotsAround(p: Point, w: number, h: number, order: Direction[]): Box[] {
  const spots: Box[] = [];
  for (const d of [8, 16, 28, 42, 60, 80]) {
    const k = d * 0.7;
    for (const dir of order) {
      const corners: Record<Direction, Point[]> = {
        above: [0.5, 0.25, 0.75].map((f) => ({ x: p.x - w * f, y: p.y - d - h })),
        below: [0.5, 0.25, 0.75].map((f) => ({ x: p.x - w * f, y: p.y + d })),
        left: [{ x: p.x - d - w, y: p.y - h / 2 }],
        right: [{ x: p.x + d, y: p.y - h / 2 }],
        aboveLeft: [{ x: p.x - k - w, y: p.y - k - h }],
        aboveRight: [{ x: p.x + k, y: p.y - k - h }],
        belowLeft: [{ x: p.x - k - w, y: p.y + k }],
        belowRight: [{ x: p.x + k, y: p.y + k }],
      };
      for (const corner of corners[dir]) spots.push({ ...corner, w, h });
    }
  }
  return spots;
}

/**
 * Where each pencil note goes on the chart: next to the point it describes,
 * clear of the line, the dots, the dashed alert line, the arrow and each
 * other, inside the plot area. The "lowest" note sits near the gold dot, with
 * an arrow from the note's edge to the dot that doesn't cross the line. The
 * alert price is written on its dashed line. If any note can't be placed:
 * { fits: false }, and the notes go in a row under the chart instead.
 */
export function layoutNotes(scene: NoteScene): NoteLayout {
  const { frame, measure, lowest: dot } = scene;
  const segments = stepSegments(scene.line);
  const placed: PlacedNote[] = [];
  let arrow: { from: Point; to: Point } | null = null;

  const inside = (b: Box) =>
    b.x >= frame.left && b.x + b.w <= frame.right && b.y >= frame.top && b.y + b.h <= frame.bottom;

  const clear = (b: Box, onAlertLine = false) => {
    const room = grow(b, CLEARANCE);
    // The line is 2.5px wide: keep clear of its edge, not just its centre.
    if (segments.some(([p, q]) => segmentHitsBox(p, q, grow(room, 1.5)))) return false;
    if (scene.dots.some((d) => boxesOverlap(room, grow({ x: d.x, y: d.y, w: 0, h: 0 }, d.r))))
      return false;
    if (!onAlertLine && scene.alertY !== null) {
      const y = scene.alertY;
      if (room.y < y + 1 && room.y + room.h > y - 1) return false;
    }
    if (placed.some((n) => boxesOverlap(room, n.box))) return false;
    if (arrow && segmentHitsBox(arrow.from, arrow.to, room)) return false;
    return true;
  };

  // The arrow from the note's edge to the dot must not cross the line on the
  // way. Its last few px meet the dot, which sits on the line, so those don't count.
  const arrowFits = (b: Box) => {
    const from = nearestOnEdge(b, dot);
    const length = Math.hypot(dot.x - from.x, dot.y - from.y);
    if (length > NEAR || length < ARROW_MIN) return false;
    const stop = (length - dot.r - 6) / length;
    const end = { x: from.x + (dot.x - from.x) * stop, y: from.y + (dot.y - from.y) * stop };
    return !segments.some(([p, q]) => crosses(from, end, p, q));
  };

  const order: PencilNote["kind"][] = ["lowest", "alert", "highest", "low30"];
  const notes = [...scene.notes].sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));

  for (const note of notes) {
    const { w, h } = measure(note.text);
    let spot: Box | undefined;

    if (note.kind === "alert") {
      if (scene.alertY === null) return { fits: false };
      const y = scene.alertY;
      const xs: number[] = [];
      for (let x = frame.right - w; x >= frame.left; x -= 16) xs.push(x);
      // Written on the line: just above it, or else just below it.
      spot = [y - 3 - h, y + 3]
        .flatMap((top) => xs.map((x) => ({ x, y: top, w, h })))
        .find((b) => inside(b) && clear(b, true));
    } else if (note.kind === "lowest") {
      spot = spotsAround(dot, w, h, PREFERENCE.lowest).find(
        (b) => inside(b) && clear(b) && arrowFits(b),
      );
      if (spot) arrow = { from: nearestOnEdge(spot, dot), to: { x: dot.x, y: dot.y } };
    } else if (note.at) {
      spot = spotsAround(note.at, w, h, PREFERENCE[note.kind]).find((b) => inside(b) && clear(b));
    }

    if (!spot) return { fits: false };
    placed.push({ kind: note.kind, text: note.text, box: spot });
  }

  return arrow ? { fits: true, notes: placed, arrow } : { fits: false };
}

// --- the subtitle ---------------------------------------------------------------

/** Subtitles are read at a glance, like film subtitles: one short line. */
export const SUBTITLE_MAX = 60;

// Sizes and counts at the end of a name: "150 ml", "1 l", "500 g", ", 90 tablets", "60 pcs".
const SIZE = /[\s,]+\d+(?:[.,]\d+)?\s*(?:ml|l|g|kg|mg|oz|pcs|adet|caps|capsules|tablets|tabs|sachets)\.?$/i;

/** "Some By Mi AHA BHA PHA Toner 150 ml" -> "AHA BHA PHA Toner": no brand, no size. */
export function shortName(name: string, brand: string | null = null): string {
  let short = name.trim();
  while (SIZE.test(short)) short = short.replace(SIZE, "");
  if (brand && short.toLowerCase().startsWith(`${brand.toLowerCase()} `))
    short = short.slice(brand.length).trim();
  return short || name.trim();
}

/** Drop words from the end of a name until the sentence fits. */
function fit(make: (name: string) => string, name: string): string {
  const words = name.split(" ");
  for (let n = words.length; n > 1; n--) {
    const line = make(words.slice(0, n).join(" "));
    if (line.length <= SUBTITLE_MAX) return line;
  }
  return make(words[0]);
}

/** The first sentence that fits in a subtitle, most detailed first. */
function firstThatFits(name: string, makers: ((name: string) => string)[]): string {
  const fits = makers.map((make) => make(name)).find((line) => line.length <= SUBTITLE_MAX);
  return fits ?? fit(makers[makers.length - 1], name);
}

/** One film-subtitle sentence, at most about 60 characters, with the most important news. */
export function newsLine(products: Product[], storeName: (key: string) => string): string {
  if (products.length === 0) return "No lights on yet. Pin a window to track a price.";

  const states = products.map((p) => ({ p, state: windowState(p, storeName(p.store)) }));
  const fakes = states.filter((x) => x.state.kind === "fake");
  const deals = states.filter((x) => x.state.kind === "deal");
  const feature = pickFeature(deals.map((x) => x.p));
  const best = deals.find((x) => x.p.id === feature?.id);

  if (best) {
    const store = storeName(best.p.store);
    // "lowest ever" -> "is at its lowest ever"; "down 3.0%" -> "is down 3.0%".
    const words = best.state.words.startsWith("lowest")
      ? `at its ${best.state.words}`
      : best.state.words;
    const but =
      fakes.length === 0 ? "" : fakes.length === 1 ? ", but one sale is fake" : `, but ${fakes.length} sales are fake`;
    return firstThatFits(shortName(best.p.name, best.p.brand), [
      (n) => `${n} is ${words} at ${store}${but}.`,
      (n) => `${n} is ${words}${but}.`,
      (n) => `${n}: ${best.state.words}${but}.`,
    ]);
  }
  if (fakes.length === 1) {
    const { p } = fakes[0];
    const store = storeName(p.store);
    return firstThatFits(shortName(p.name, p.brand), [
      (n) => `The sale on ${n} at ${store} is fake: it went up first.`,
      (n) => `The sale on ${n} is fake: it went up first.`,
      (n) => `The sale on ${n} is fake.`,
    ]);
  }
  if (fakes.length > 1) return `${fakes.length} sales tonight are fake: prices went up first.`;
  return "A quiet night. Nothing on your list got cheaper.";
}

// --- scatter ----------------------------------------------------------------------

export interface Placement {
  /** Degrees, between -3 and 3. */
  rotate: number;
  /** Width as a share of the column, 0.62 to 1. */
  size: number;
  /** Sideways nudge as a share of the free space, -1 (left) to 1 (right). */
  nudge: number;
  /** Drop from the top of the row in px, 0 to 120 (scaled down on small screens). */
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
    size: round(0.62 + next() * 0.38),
    nudge: round(next() * 2 - 1),
    drop: Math.round(next() * 120),
    tape: Math.round(next() * 16 - 8),
  };
}

// --- chart axis ---------------------------------------------------------------------

export interface TimeAxis {
  /** "day": one tick per day, labelled "10 Nov". "time": labelled "09:17". */
  kind: "day" | "time";
  /** The x range to draw: from the first check to the last, so the line fills the width. */
  domain: [Date, Date];
  ticks: Date[];
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const minuteKey = (d: Date) => `${d.getHours()}:${d.getMinutes()}`;

/** Steps between day ticks, smallest first. */
const DAY_STEPS = [1, 2, 3, 4, 7, 14, 28, 56, 91, 182, 364];

/**
 * Ticks for the price chart's time axis, at most one per day, so a label never
 * repeats. When every check falls on one day, the ticks are the check times.
 * `maxTicks` is how many labels fit across the chart.
 */
export function timeAxis(dates: Date[], maxTicks: number): TimeAxis {
  const sorted = [...dates].sort((a, b) => a.getTime() - b.getTime());
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const fit = Math.max(2, Math.floor(maxTicks));

  if (startOfDay(first).getTime() === startOfDay(last).getTime()) {
    const seen = new Set<string>();
    const times = sorted.filter((d) => !seen.has(minuteKey(d)) && seen.add(minuteKey(d)));
    const every = Math.ceil(times.length / fit);
    return {
      kind: "time",
      domain: [first, last],
      ticks: times.filter((_, i) => i % every === 0),
    };
  }

  const firstDay = startOfDay(first);
  const days = Math.round((startOfDay(last).getTime() - firstDay.getTime()) / 86_400_000) + 1;
  const step = DAY_STEPS.find((s) => Math.ceil(days / s) <= fit) ?? Math.ceil(days / fit);
  // Each day's tick sits at its midnight, except the first day's: its midnight is
  // before the first check, so that tick sits at the first check instead.
  const candidates: Date[] = [];
  for (let i = 0; i < days; i += step) {
    const midnight = addDays(firstDay, i);
    candidates.push(midnight < first ? first : midnight);
  }
  // Labels too close together would collide (e.g. a first check at 23:50 and the
  // next midnight). Then the next midnight wins over the first check's tick.
  const minGap = (last.getTime() - first.getTime()) / Math.max(fit, candidates.length) / 2;
  const ticks: Date[] = [];
  for (const tick of candidates) {
    const before = ticks[ticks.length - 1];
    if (before === undefined || tick.getTime() - before.getTime() >= minGap) ticks.push(tick);
    else if (ticks.length === 1) ticks[0] = tick;
  }
  return { kind: "day", domain: [first, last], ticks };
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

export interface ChoiceGroup {
  label: string;
  products: Product[];
}

/**
 * Products that could be linked with this one: not itself, nothing already in its group.
 * Same room first, then the rest by floor (in floor order, then room, then name).
 */
export function linkChoices(
  categories: Category[],
  products: Product[],
  product: Product,
  linkedIds: number[],
): ChoiceGroup[] {
  const taken = new Set([product.id, ...linkedIds]);
  const candidates = products.filter((p) => !taken.has(p.id));
  const room = roomOf(categories, product);
  const sameRoom = room
    ? candidates.filter((p) => p.category_id === room.id).sort((a, b) => a.name.localeCompare(b.name))
    : [];
  const rest = candidates.filter((p) => !sameRoom.includes(p));

  const groups: ChoiceGroup[] = [];
  if (room && sameRoom.length) groups.push({ label: `Same room (${room.name})`, products: sameRoom });
  for (const { floor, products: onFloor } of floorsOf(categories, rest)) {
    if (onFloor.length) groups.push({ label: floor?.name ?? "No floor yet", products: onFloor });
  }
  return groups;
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

const INK = "#141414";
const WHITE = "#FFFFFF";

/** Text colour for a label printed on a user-chosen floor colour. */
export function inkOn(background: string): string {
  return contrast(background, INK) >= contrast(background, WHITE) ? INK : WHITE;
}

// --- notes ----------------------------------------------------------------------------

/** What a note is about, in words: the label at the top of each note. */
export const NOTE_LABELS: Record<NoteKind, string> = {
  target: "alert price reached",
  lowest: "lowest ever",
  fake_sale: "fake sale",
  cheaper: "cheaper elsewhere",
  back_in_stock: "back in stock",
  sunday_paper: "sunday paper",
};

export type Tone = "deal" | "warning" | "plain";

/** Mustard for good deals, rouge for warnings, plain paper for the rest. */
export function noteTone(kind: NoteKind): Tone {
  if (kind === "fake_sale") return "warning";
  return kind === "back_in_stock" || kind === "sunday_paper" ? "plain" : "deal";
}

// --- the Sunday paper -------------------------------------------------------------------

export type PaperSectionKey = "drops" | "new_lows" | "fake_sales" | "cheaper" | "rises" | "trouble";

export interface PaperSection {
  key: PaperSectionKey;
  /** Lowercase, like a poster headline: "new lows". */
  title: string;
  tone: Tone;
  /** A short handwritten margin note, or null. */
  hand: string | null;
  /** How many items the section has (the lead story isn't one of the drops here). */
  count: number;
  /** How many of them fit when printed; "and 2 more" covers the rest. */
  printed: number;
}

/** On one printed A4 page, each section shows at most this many items. */
export const PRINT_LIMIT = 5;

const SECTIONS: { key: PaperSectionKey; title: string; tone: Tone; hand: string | null }[] = [
  { key: "drops", title: "more drops", tone: "deal", hand: null },
  { key: "new_lows", title: "new lows", tone: "deal", hand: "lowest ever!" },
  { key: "fake_sales", title: "fake sales caught", tone: "warning", hand: "not really cheaper" },
  { key: "cheaper", title: "cheaper elsewhere", tone: "deal", hand: null },
  { key: "rises", title: "price rises", tone: "plain", hand: null },
  { key: "trouble", title: "failed checks and sold out", tone: "plain", hand: null },
];

/**
 * The paper's sections in reading order, leaving out the empty ones. The biggest drop is
 * the lead story at the top, so "more drops" holds the others.
 */
export function paperSections(paper: Paper): PaperSection[] {
  return SECTIONS.map((s) => {
    const count = s.key === "drops" ? Math.max(paper.drops.length - 1, 0) : paper[s.key].length;
    return { ...s, count, printed: Math.min(count, PRINT_LIMIT) };
  }).filter((s) => s.count > 0);
}

/** The lead story: the biggest drop of the week, if anything got cheaper. */
export function paperLead(paper: Paper): PaperMove | null {
  return paper.drops[0] ?? null;
}

/** One calm line when nothing happened; null when there's news. */
export function quietWeekLine(paper: Paper): string | null {
  if (paperLead(paper) || paperSections(paper).length > 0) return null;
  if (paper.products_checked === 0) return "No prices were checked this week, so there's no news.";
  return "A quiet week. No price moved, and every check went through.";
}

/** "16 products checked" under the dateline. */
export function checkedLine(count: number): string {
  return count === 1 ? "1 product checked" : `${count} products checked`;
}

/** "down 12.0%" or "up 3.0%", in words. */
export function moveWords(pct: number): string {
  return `${pct < 0 ? "down" : "up"} ${formatChange(pct).slice(1)}`;
}

// --- best time to buy -------------------------------------------------------------------

/** 1 -> "1st", 2 -> "2nd", 11 -> "11th", 22 -> "22nd". */
export function ordinal(n: number): string {
  const teen = n % 100 >= 11 && n % 100 <= 13;
  const suffix = teen ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

const WEEKDAY_NAMES = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"];

function both(items: string[]): string {
  return items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}` : items[0];
}

/** "~5 weeks", or "~10 days" for gaps under two weeks. */
function about(days: number): string {
  return days >= 14 ? `~${Math.round(days / 7)} weeks` : `~${days} days`;
}

function ago(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  return `${Math.round(days / 7)} weeks ago`;
}

/**
 * The handwritten note on when a product has been cheapest, from its own history. It says
 * what has been, never what will be, and only patterns that would have helped come from the
 * backend.
 */
export function bestTimeNote(best: BestTime): string {
  if (!best.enough_history) return "Not enough history yet.";
  const sentences: string[] = [];
  if (best.days_of_month.length)
    sentences.push(`Has usually been cheapest around the ${both(best.days_of_month.map(ordinal))}.`);
  if (best.weekdays.length)
    sentences.push(`Has usually been cheapest on ${both(best.weekdays.map((w) => WEEKDAY_NAMES[w]))}.`);
  const cycle = best.sale_cycle;
  if (cycle)
    sentences.push(
      `Real sales have come every ${about(cycle.every_days)}, usually ${Math.round(cycle.typical_pct)}% off; ` +
        `the last one ${ago(cycle.last_days_ago)}.`,
    );
  for (const event of best.events) sentences.push(`${event.name} was ${Math.round(event.pct)}% off.`);
  return sentences.length ? sentences.join(" ") : "No timing pattern has paid off for this one so far.";
}

/** The backtest in one line: "Looking back, waiting for these times paid less on 86 of 103 days, 9.5% less on average." */
export function backtestLine(backtest: Backtest | null): string {
  if (!backtest) return "";
  const { wins, trials, average_saving_pct: saving } = backtest;
  return `Looking back, waiting for ${trials === 1 ? "this time" : "these times"} paid less on ${wins} of ${trials} days, ${saving.toFixed(1)}% less on average.`;
}

const demoDay = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** The header's reminder that PD_TODAY is set: "demo date: 1 Dec 2026", or nothing. */
export function demoDateLabel(setDate: string | null | undefined): string {
  return setDate ? `demo date: ${demoDay.format(parseDay(setDate))}` : "";
}

/** The header's count: "2 new", or nothing when every note is read. */
export function unreadLabel(unread: number): string {
  return unread > 0 ? `${unread} new` : "";
}
