import type { CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { Category, Product } from "../api";
import { NightWindow } from "../components/NightWindow";
import { QuietItem } from "../components/QuietItem";
import { WindowDrawing } from "../components/WindowDrawing";
import { useCategories, useProducts, useStores } from "../hooks";
import { useMode } from "../mode";
import { floorsOf, inkOn, newsLine, placement, roomOf, type Floor } from "../scene";

export function IndexPage() {
  const products = useProducts();
  const categories = useCategories();
  const storeName = useStoreName();
  const [params] = useSearchParams();
  const { mode } = useMode();

  if (products.isLoading || categories.isLoading)
    return <p className="status">Turning the lights on…</p>;
  if (products.error || categories.error)
    return (
      <p className="status status--error">
        Can't reach the tracker. Start the backend with <code>uv run price-diaries serve</code>.
      </p>
    );

  const all = products.data ?? [];
  const cats = categories.data ?? [];
  const floors = floorsOf(cats, all);
  const chosen = floors.find((f) => f.floor && String(f.floor.id) === params.get("floor"));
  const shown = chosen ? [chosen] : floors;
  const shownProducts = shown.flatMap((f) => f.products);
  // An empty floor already says so; the subtitle then tells the news of the whole building.
  const news = newsLine(shownProducts.length > 0 ? shownProducts : all, storeName);

  if (all.length === 0) return <EmptyBuilding quiet={mode === "quiet"} />;

  if (mode === "quiet")
    return (
      <div className="quiet">
        <PosterTitle />
        <p className="poster-summary">{news}</p>
        <FloorTabs floors={floors} current={chosen?.floor ?? null} />
        {shown.map((f) => (
          <QuietFloor
            key={f.floor?.id ?? "none"}
            floor={f}
            categories={cats}
            storeName={storeName}
            labelled={!chosen}
          />
        ))}
      </div>
    );

  return (
    <div className="night">
      <Masthead />
      <FloorTabs floors={floors} current={chosen?.floor ?? null} />
      <Headline floor={chosen?.floor ?? null} />

      <div className="building">
        {shown.map((f) => (
          <FloorSection
            key={f.floor?.id ?? "none"}
            floor={f}
            categories={cats}
            storeName={storeName}
            labelled={!chosen}
          />
        ))}
      </div>

      <p className="subtitle">
        <span>{news}</span>
      </p>
    </div>
  );
}

/** Quiet mode's title: the full name, with a small "the" above, like the night masthead. */
function PosterTitle() {
  return (
    <h1 className="poster-title">
      <span className="poster-title__the">the</span> <span>price diaries</span>
    </h1>
  );
}

function Masthead() {
  return (
    <div className="masthead">
      <h1 className="masthead__title">
        <span className="masthead__the">the price</span>{" "}
        <span className="masthead__diaries">
          diaries
          <span className="masthead__panes" aria-hidden="true">
            diaries
          </span>
        </span>
      </h1>
    </div>
  );
}

function FloorTabs({ floors, current }: { floors: Floor[]; current: Category | null }) {
  const named = floors.filter((f): f is Floor & { floor: Category } => f.floor !== null);
  return (
    <nav className="floor-tabs" aria-label="Floors">
      <ul>
        <li style={{ "--tilt": "-1.5deg" } as CSSProperties}>
          <Link className="floor-tab" to="/" aria-current={current === null ? "page" : undefined}>
            everything
          </Link>
        </li>
        {named.map(({ floor, products }) => (
          <li
            key={floor.id}
            style={
              {
                "--tilt": `${placement(floor.id).rotate * 0.7}deg`,
                "--tape-angle": `${placement(floor.id).tape}deg`,
                "--strip": floor.color,
                "--strip-ink": inkOn(floor.color),
              } as CSSProperties
            }
          >
            <Link
              className="floor-tab floor-tab--colored"
              to={`/?floor=${floor.id}`}
              aria-current={current?.id === floor.id ? "page" : undefined}
            >
              {floor.name.toLowerCase()}
              <span className="floor-tab__count">
                {products.length}
                <span className="visually-hidden"> {products.length === 1 ? "product" : "products"}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** "tonight on the ▯ skincare ▯ floor", with tiny lit windows between words. */
function Headline({ floor }: { floor: Category | null }) {
  const lit = <span className="tiny-window" aria-hidden="true" />;
  return (
    <h2 className="tonight">
      {floor ? (
        <>
          tonight on the {lit} {floor.name.toLowerCase()} {lit} floor
        </>
      ) : (
        <>
          tonight in the {lit} whole {lit} building
        </>
      )}
    </h2>
  );
}

function FloorSection(props: {
  floor: Floor;
  categories: Category[];
  storeName: (key: string) => string;
  labelled: boolean;
}) {
  const { floor, products } = props.floor;
  const id = `floor-${floor?.id ?? "none"}`;
  const name = floor ? floor.name.toLowerCase() : "no floor yet";
  return (
    <section className="floor" aria-labelledby={id}>
      <h3
        id={id}
        className={`floor__sign paper paper--taped ${props.labelled ? "" : "visually-hidden"}`}
        style={
          floor
            ? ({ "--strip": floor.color, "--strip-ink": inkOn(floor.color) } as CSSProperties)
            : undefined
        }
      >
        {name}
      </h3>
      {products.length > 0 ? (
        <ol className="windows">
          {products.map((p: Product) => (
            <NightWindow
              key={p.id}
              product={p}
              storeName={props.storeName(p.store)}
              room={roomOf(props.categories, p)}
            />
          ))}
        </ol>
      ) : (
        <>
          <DarkWindows count={3} />
          <p className="floor__empty">No lights on this floor yet.</p>
        </>
      )}
    </section>
  );
}

function QuietFloor(props: {
  floor: Floor;
  categories: Category[];
  storeName: (key: string) => string;
  labelled: boolean;
}) {
  const { floor, products } = props.floor;
  const id = `quiet-floor-${floor?.id ?? "none"}`;
  return (
    <section className="poster-floor" aria-labelledby={id}>
      <h2 id={id} className={`poster-floor__name ${props.labelled ? "" : "visually-hidden"}`}>
        {floor ? floor.name.toLowerCase() : "no floor yet"}
      </h2>
      {products.length > 0 ? (
        <ol className="poster-list">
          {products.map((p) => (
            <QuietItem
              key={p.id}
              product={p}
              storeName={props.storeName(p.store)}
              room={roomOf(props.categories, p)}
            />
          ))}
        </ol>
      ) : (
        <p className="poster-floor__empty">Nothing tracked on this floor yet.</p>
      )}
    </section>
  );
}

/** Nothing tracked yet: the whole building is dark. */
function EmptyBuilding({ quiet }: { quiet: boolean }) {
  if (quiet)
    return (
      <div className="quiet">
        <PosterTitle />
        <p className="poster-summary">Nothing tracked yet.</p>
        <p className="empty-actions">
          <Link className="paper-button" to="/add">
            Pin a new window
          </Link>
        </p>
      </div>
    );
  return (
    <div className="night">
      <Masthead />
      <div className="building building--dark">
        <DarkWindows count={8} />
        <h2 className="tonight">no lights on yet</h2>
        <p className="floor__empty">
          Pin a product's window and its light comes on when the price is worth a look.
        </p>
        <p className="empty-actions">
          <Link className="paper-button paper-button--mustard" to="/add">
            Pin a new window
          </Link>
        </p>
      </div>
    </div>
  );
}

/** Unlit windows, for empty floors and the empty building. Decorative. */
function DarkWindows({ count }: { count: number }) {
  return (
    <div className="dark-windows" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <span key={i} className="dark-windows__one">
          <WindowDrawing kind="waiting" />
        </span>
      ))}
    </div>
  );
}

function useStoreName(): (key: string) => string {
  const { data: stores = [] } = useStores();
  return (key) => stores.find((s) => s.key === key)?.name ?? key;
}
