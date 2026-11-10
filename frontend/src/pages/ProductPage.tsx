import { lazy, Suspense, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { LinerNotes } from "../components/LinerNotes";
import { PencilCircle, PencilX } from "../components/Pencil";
import { Price, RegularPriceNote } from "../components/Price";
import { ProductPhoto } from "../components/ProductPhoto";
import { formatDate, insight } from "../format";
import {
  useCategories,
  useCheckOne,
  useProduct,
  useRemoveProduct,
  useSetTarget,
  useStores,
} from "../hooks";
import { useMode } from "../mode";
import { roomOf, windowState } from "../scene";

// Observable Plot is the largest dependency, so load it only on this page.
const PriceChart = lazy(() =>
  import("../components/PriceChart").then((m) => ({ default: m.PriceChart })),
);

/** One product, "inside the room". */
export function ProductPage() {
  const id = Number(useParams().id);
  const { data: product, isLoading, error } = useProduct(id);
  const { data: stores = [] } = useStores();
  const { data: categories = [] } = useCategories();
  const { mode } = useMode();
  const check = useCheckOne();
  const remove = useRemoveProduct();
  const navigate = useNavigate();

  if (isLoading) return <p className="status">Opening the door…</p>;
  if (error || !product)
    return (
      <p className="status status--error">
        This product isn't tracked any more. <Link to="/">Back to the building</Link>
      </p>
    );

  const s = product.summary;
  const storeName = stores.find((st) => st.key === product.store)?.name ?? product.store;
  const room = roomOf(categories, product);
  const state = windowState(product, storeName);
  const quiet = mode === "quiet";

  async function stopTracking() {
    if (!window.confirm(`Stop tracking ${product!.name}? Its price history will be deleted.`)) return;
    await remove.mutateAsync(product!.id);
    navigate("/");
  }

  return (
    <article className={`room room--${state.kind}`}>
      <Link className="room__back text-button" to="/">
        Back to the building
      </Link>

      <div className="room__stage">
        <div className="room__window" aria-hidden="true">
          {quiet ? (
            <span className="room__poster-image">
              <ProductPhoto src={product.image_url} hint={`${room?.name ?? ""} ${product.name}`} />
              {state.kind === "fake" && <PencilX />}
            </span>
          ) : (
            <span className="window window--big">
              <span className="window__glass">
                <ProductPhoto
                  src={product.image_url}
                  hint={`${room?.name ?? ""} ${product.name}`}
                  className="window__photo"
                />
              </span>
              <span className="curtain curtain--left" />
              <span className="curtain curtain--right" />
              {state.kind === "blocked" && <span className="blinds" />}
            </span>
          )}
        </div>

        <div className="room__credits">
          <p className="room__presents">{storeName} presents</p>
          <h1 className="room__name">{product.name}</h1>
          {room && <p className="room__where">{room.name.toLowerCase()}</p>}

          {s && (
            <div className="room__price paper paper--taped">
              <span className="room__price-figure">
                <Price value={s.current} size="hero" />
                {quiet && state.kind === "deal" && <PencilCircle />}
              </span>
              <RegularPriceNote regular={product.regular_price} />
            </div>
          )}

          <p className={quiet && (state.kind === "deal" || state.kind === "fake") ? "hand-note" : "room__state"}>
            {quiet && state.kind === "fake" ? "fake sale, skip" : quiet && state.kind === "deal" ? `${state.words}!` : state.words}
          </p>
          <p className="room__insight">{insight(product)}</p>

          <div className="room__actions">
            <button
              type="button"
              className="paper-button paper-button--mustard"
              onClick={() => check.mutate(product.id)}
              disabled={check.isPending}
            >
              {check.isPending ? "Checking…" : "Check price now"}
            </button>
            <a className="paper-button" href={product.url} target="_blank" rel="noreferrer noopener">
              Open at {storeName}
            </a>
          </div>
          {check.data && !check.data.ok && (
            <p className="room__error" role="alert">
              {check.data.error}
            </p>
          )}
          {check.data?.ok && (
            <p className="room__checked" role="status">
              Checked just now.
            </p>
          )}
        </div>
      </div>

      {s && (
        <dl className="facts">
          <Fact label="Lowest" value={s.lowest} note={formatDate(s.lowest_at)} />
          <Fact label="Highest" value={s.highest} note={formatDate(s.highest_at)} />
          <Fact label="Lowest in 30 days" value={s.lowest_30d} />
          <AlertFact id={product.id} target={product.target_price} />
        </dl>
      )}

      {product.history.length > 0 ? (
        <section className="torn" aria-label="Price chart">
          <Suspense fallback={<div className="chart__canvas" />}>
            <PriceChart
              history={product.history}
              anomalies={product.anomalies}
              target={product.target_price}
            />
          </Suspense>
        </section>
      ) : (
        <p className="status">The chart appears after the first price check.</p>
      )}

      {product.history.length > 0 && (
        <LinerNotes history={product.history} anomalies={product.anomalies} />
      )}

      <p className="room__stop">
        <button type="button" className="text-button" onClick={stopTracking}>
          Stop tracking
        </button>
      </p>
    </article>
  );
}

function Fact({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>
        <Price value={value} size="large" />
        {note && <span className="fact__note">{note}</span>}
      </dd>
    </div>
  );
}

function AlertFact({ id, target }: { id: number; target: number | null }) {
  const setTarget = useSetTarget();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(target ? String(target).replace(".", ",") : "");
  const [error, setError] = useState<string | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    const number = Number(value.replace(",", "."));
    if (!number || number <= 0) {
      setError("Enter a price, like 249,90.");
      return;
    }
    await setTarget.mutateAsync({ id, target: number });
    setEditing(false);
    setError(null);
  }

  return (
    <div className="fact">
      <dt>Alert price</dt>
      <dd>
        {editing ? (
          <form className="alert-form" onSubmit={save}>
            <input
              aria-label="Alert price"
              inputMode="decimal"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError(null);
              }}
              autoFocus
            />
            <button className="paper-button paper-button--mustard" type="submit">
              Save alert price
            </button>
            {error && (
              <span className="fact__error" role="alert">
                {error}
              </span>
            )}
          </form>
        ) : (
          <>
            {target ? <Price value={target} size="large" /> : <span className="fact__none">None set</span>}
            <button type="button" className="text-button" onClick={() => setEditing(true)}>
              {target ? "Change alert price" : "Set an alert price"}
            </button>
          </>
        )}
      </dd>
    </div>
  );
}
