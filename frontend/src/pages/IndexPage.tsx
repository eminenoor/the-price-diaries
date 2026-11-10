import { Link } from "react-router-dom";

import type { Product } from "../api";
import { AddProductForm } from "../components/AddProductForm";
import { Price, RegularPriceNote } from "../components/Price";
import { Sparkline } from "../components/Sparkline";
import { formatChange, insight, pickFeature } from "../format";
import { useProducts, useStores } from "../hooks";

export function IndexPage() {
  const { data: products = [], isLoading, error } = useProducts();
  const visible = products;
  const feature = pickFeature(products);

  if (isLoading) return <p className="status">Loading your products…</p>;
  if (error)
    return (
      <p className="status status--error">
        Can't reach the tracker. Start the backend with <code>uv run price-diaries serve</code>.
      </p>
    );

  return (
    <>
      {feature?.summary ? <Feature product={feature} /> : <Welcome />}
      <AddProductForm />

      {products.length > 0 && (
        <section className="index" aria-labelledby="index-title">
          <div className="index__head">
            <h2 id="index-title" className="index__title">
              Everything you're watching
            </h2>
          </div>
          <ol className="rows">
            {visible.map((p) => (
              <ProductRow key={p.id} product={p} />
            ))}
          </ol>
        </section>
      )}
    </>
  );
}

function Feature({ product }: { product: Product }) {
  const s = product.summary!;
  const storeName = useStoreName(product.store);
  return (
    <section className="feature" aria-label="Best deal right now">
      <div className="feature__copy">
        <p className="feature__kicker">The best deal on your list today</p>
        <h1 className="feature__name">
          <Link to={`/products/${product.id}`}>{product.name}</Link>
        </h1>
        <p className="feature__meta">at {storeName}</p>
        <p className="feature__insight">{insight(product)}</p>
      </div>
      <div className="feature__figure">
        <Price value={s.current} size="hero" />
        <RegularPriceNote regular={product.regular_price} />
        <Sparkline
          values={product.sparkline}
          width={320}
          height={72}
          label={`Price trend for ${product.name}`}
        />
        <p className="feature__range">
          It has been as high as <Price value={s.highest} />
        </p>
      </div>
    </section>
  );
}

function Welcome() {
  return (
    <section className="feature feature--empty">
      <h1 className="feature__name">Your price diary</h1>
      <p className="feature__insight">
        Paste a product link below. Its price is checked every morning and every check is kept, so
        you can see when a "sale" isn&apos;t really one.
      </p>
    </section>
  );
}

function ProductRow({ product }: { product: Product }) {
  const s = product.summary;
  const storeName = useStoreName(product.store);
  const tone = !s ? "" : s.fake_sale ? "row--warning" : s.is_all_time_low ? "row--good" : "";
  return (
    <li className={`row ${tone}`}>
      <Link className="row__link" to={`/products/${product.id}`}>
        <span className="row__name">{product.name}</span>
        <span className="row__store">
          {storeName}
        </span>
      </Link>
      <Sparkline values={product.sparkline} label={`Price trend for ${product.name}`} />
      <span className="row__price">
        {s ? <Price value={s.current} size="large" /> : <span className="row__pending">Not checked yet</span>}
        <RegularPriceNote regular={product.regular_price} />
        {s?.change_pct ? (
          <span className={`row__change ${s.change_pct < 0 ? "is-down" : "is-up"}`}>
            {formatChange(s.change_pct)}
          </span>
        ) : null}
      </span>
      <p className="row__insight">{insight(product)}</p>
    </li>
  );
}


function useStoreName(key: string): string {
  const { data: stores = [] } = useStores();
  return stores.find((s) => s.key === key)?.name ?? key;
}
