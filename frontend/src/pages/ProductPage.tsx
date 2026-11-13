import { lazy, Suspense, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { Size } from "../api";
import { Elsewhere } from "../components/Elsewhere";
import { LinerNotes } from "../components/LinerNotes";
import { PencilCircle, PencilX } from "../components/Pencil";
import { Price, RegularPriceNote, UnitPrice } from "../components/Price";
import { ProductPhoto } from "../components/ProductPhoto";
import { WindowDrawing } from "../components/WindowDrawing";
import { formatSize, insight } from "../format";
import {
  useCategories,
  useCheckOne,
  useProduct,
  useRemoveProduct,
  useSetBrand,
  useSetSize,
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
            <WindowDrawing
              big
              kind={state.kind}
              photo={{ src: product.image_url, hint: `${room?.name ?? ""} ${product.name}` }}
            />
          )}
        </div>

        <div className="room__credits">
          {product.brand && <p className="room__presents">{product.brand} presents</p>}
          <h1 className="room__name">{product.name}</h1>
          {room && <p className="room__where">{room.name.toLowerCase()}</p>}

          {s && (
            <div className="room__price paper paper--taped">
              <span className="room__price-figure">
                <Price value={s.current} size="hero" />
                {quiet && state.kind === "deal" && <PencilCircle />}
              </span>
              <RegularPriceNote regular={product.regular_price} />
              <UnitPrice unit={product.unit_price} />
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

      <Elsewhere product={product} />

      {product.history.length === 1 ? (
        <p className="chart-note">the chart starts after a few days of checks</p>
      ) : product.history.length > 1 && s ? (
        <section className="torn" aria-label="Price chart">
          <Suspense fallback={<div className="chart__canvas" />}>
            <PriceChart
              history={product.history}
              anomalies={product.anomalies}
              summary={s}
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

      <div className="room__edit">
        {/* Without a chart there's no dashed line to write the alert price on. */}
        <AlertEditor
          id={product.id}
          target={product.target_price}
          showValue={product.history.length < 2}
        />
        <BrandEditor id={product.id} brand={product.brand} />
        <SizeEditor id={product.id} size={product.size} />
        <p className="room__stop">
          <button type="button" className="text-button" onClick={stopTracking}>
            Stop tracking
          </button>
        </p>
      </div>
    </article>
  );
}

/** The brand comes from the store page; stores sometimes get it wrong, so it can be changed. */
function BrandEditor({ id, brand }: { id: number; brand: string | null }) {
  const setBrand = useSetBrand();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(brand ?? "");

  async function save(event: FormEvent) {
    event.preventDefault();
    await setBrand.mutateAsync({ id, brand: value.trim() });
    setEditing(false);
  }

  if (!editing)
    return (
      <button
        type="button"
        className="text-button"
        onClick={() => {
          setValue(brand ?? "");
          setEditing(true);
        }}
      >
        {brand ? "Change brand" : "Add the brand"}
      </button>
    );
  return (
    <form className="edit-form" onSubmit={save}>
      <label>
        Brand
        <input value={value} maxLength={100} onChange={(e) => setValue(e.target.value)} autoFocus />
      </label>
      <button className="paper-button paper-button--mustard" type="submit" disabled={setBrand.isPending}>
        {value.trim() ? "Save brand" : "Remove brand"}
      </button>
      <button type="button" className="text-button" onClick={() => setEditing(false)}>
        Cancel
      </button>
    </form>
  );
}

/**
 * The pack size is read from the name or the store page, which can be wrong, so it can be
 * changed. The backend reads what's typed the same way it reads names ("1,5 L", "60 adet").
 */
function SizeEditor({ id, size }: { id: number; size: Size | null }) {
  const setSize = useSetSize();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await setSize.mutateAsync({ id, size: value.trim() });
      setEditing(false);
    } catch {
      // The error is shown below the form.
    }
  }

  if (!editing)
    return (
      <span className="edit-row__item">
        {size && <span>Size {formatSize(size)}</span>}
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setValue(size ? formatSize(size) : "");
            setSize.reset();
            setEditing(true);
          }}
        >
          {size ? "Change size" : "Add the size"}
        </button>
      </span>
    );
  return (
    <form className="edit-form" onSubmit={save}>
      <label>
        Size
        <input
          value={value}
          maxLength={50}
          placeholder="150 ml"
          onChange={(e) => {
            setValue(e.target.value);
            setSize.reset();
          }}
          autoFocus
        />
      </label>
      <button className="paper-button paper-button--mustard" type="submit" disabled={setSize.isPending}>
        {value.trim() ? "Save size" : "Remove size"}
      </button>
      <button type="button" className="text-button" onClick={() => setEditing(false)}>
        Cancel
      </button>
      {setSize.error && (
        <span className="edit-form__error" role="alert">
          {setSize.error.message}
        </span>
      )}
    </form>
  );
}

/** The alert price is written on the chart; this changes it. */
function AlertEditor(props: { id: number; target: number | null; showValue: boolean }) {
  const { id, target, showValue } = props;
  const setTarget = useSetTarget();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
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

  if (!editing)
    return (
      <span className="edit-row__item">
        {showValue && target !== null && (
          <span>
            Alert price <Price value={target} />
          </span>
        )}
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setValue(target ? String(target).replace(".", ",") : "");
            setEditing(true);
          }}
        >
          {target ? "Change alert price" : "Set an alert price"}
        </button>
      </span>
    );
  return (
    <form className="edit-form" onSubmit={save}>
      <label>
        Alert price
        <input
          inputMode="decimal"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          autoFocus
        />
      </label>
      <button className="paper-button paper-button--mustard" type="submit" disabled={setTarget.isPending}>
        Save alert price
      </button>
      <button type="button" className="text-button" onClick={() => setEditing(false)}>
        Cancel
      </button>
      {error && (
        <span className="edit-form__error" role="alert">
          {error}
        </span>
      )}
    </form>
  );
}
