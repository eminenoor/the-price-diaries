import { lazy, Suspense, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Price, RegularPriceNote } from "../components/Price";
import { formatChange, formatDate, insight } from "../format";
import type { PricePoint } from "../api";
import { useCheckOne, useProduct, useRemoveProduct, useSetTarget, useStores } from "../hooks";

// Observable Plot is the largest dependency, so load it only on this page.
const PriceChart = lazy(() =>
  import("../components/PriceChart").then((m) => ({ default: m.PriceChart })),
);

export function ProductPage() {
  const id = Number(useParams().id);
  const { data: product, isLoading, error } = useProduct(id);
  const { data: stores = [] } = useStores();
  const check = useCheckOne();
  const remove = useRemoveProduct();
  const navigate = useNavigate();

  if (isLoading) return <p className="status">Loading…</p>;
  if (error || !product)
    return (
      <p className="status status--error">
        This product isn't tracked any more. <Link to="/">See all products</Link>
      </p>
    );

  const s = product.summary;
  const storeName = stores.find((st) => st.key === product.store)?.name ?? product.store;
  const unusual = new Set(product.anomalies.map((a) => a.checked_at));

  async function stopTracking() {
    if (!window.confirm(`Stop tracking ${product!.name}? Its price history will be deleted.`)) return;
    await remove.mutateAsync(product!.id);
    navigate("/");
  }

  return (
    <article className="detail">
      <Link className="back" to="/">
        All products
      </Link>

      <header className="detail__header">
        <div>
          <h1 className="detail__name">{product.name}</h1>
          <p className="detail__meta">
            at {storeName}
          </p>
        </div>
        {s && (
          <div className="detail__price">
            <Price value={s.current} size="hero" />
            <RegularPriceNote regular={product.regular_price} />
          </div>
        )}
      </header>

      <p className={`detail__insight ${s?.fake_sale ? "is-warning" : ""}`}>{insight(product)}</p>

      <div className="detail__actions">
        <button
          type="button"
          className="button button--primary"
          onClick={() => check.mutate(product.id)}
          disabled={check.isPending}
        >
          {check.isPending ? "Checking…" : "Check price now"}
        </button>
        <a className="button" href={product.url} target="_blank" rel="noreferrer noopener">
          Open in {storeName}
        </a>
        <button type="button" className="button button--quiet" onClick={stopTracking}>
          Stop tracking
        </button>
      </div>
      {check.data && !check.data.ok && (
        <p className="status status--error" role="alert">
          {check.data.error}
        </p>
      )}

      {product.history.length > 1 ? (
        <Suspense fallback={<div className="chart__canvas" />}>
          <PriceChart
            history={product.history}
            anomalies={product.anomalies}
            target={product.target_price}
          />
        </Suspense>
      ) : (
        <p className="status">The chart appears after the second price check.</p>
      )}

      {s && (
        <dl className="facts">
          <Fact label="Lowest" value={s.lowest} note={formatDate(s.lowest_at)} />
          <Fact label="Highest" value={s.highest} note={formatDate(s.highest_at)} />
          <Fact label="Lowest in 30 days" value={s.lowest_30d} />
          <TargetFact id={product.id} target={product.target_price} />
        </dl>
      )}

      {product.history.length > 0 && (
        <section className="log" aria-labelledby="log-title">
          <h2 id="log-title" className="log__title">
            Every check
          </h2>
          <table className="log__table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Price</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {[...product.history].reverse().map((p, i, all) => {
                const paid = (point: PricePoint) => point.member_price ?? point.price;
                const before = all[i + 1] ? paid(all[i + 1]) : undefined;
                const change = before ? ((paid(p) - before) / before) * 100 : 0;
                return (
                  <tr key={p.checked_at}>
                    <td>{formatDate(p.checked_at)}</td>
                    <td className="log__price">
                      <Price value={p.member_price ?? p.price} />
                    </td>
                    <td className="log__note">
                      {Math.abs(change) >= 0.05 && (
                        <span className={change < 0 ? "is-down" : "is-up"}>{formatChange(change)}</span>
                      )}
                      {p.member_price !== null && (
                        <span className="log__regular">
                          Regular <Price value={p.price} />
                        </span>
                      )}
                      {unusual.has(p.checked_at) && <span className="tag">Unusual rise</span>}
                      {!p.in_stock && <span className="tag">Out of stock</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
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

function TargetFact({ id, target }: { id: number; target: number | null }) {
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
      <dt>Your target</dt>
      <dd>
        {editing ? (
          <form className="target-form" onSubmit={save}>
            <input
              aria-label="Target price"
              inputMode="decimal"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError(null);
              }}
              autoFocus
            />
            <button className="button button--primary" type="submit">
              Save target
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
            <button type="button" className="link-button" onClick={() => setEditing(true)}>
              {target ? "Change target" : "Set a target"}
            </button>
          </>
        )}
      </dd>
    </div>
  );
}
