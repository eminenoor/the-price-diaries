import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import type { ElsewhereNote, Offer, ProductDetail } from "../api";
import { useLink, useProducts, useStores, useUnlink } from "../hooks";
import { Price, UnitPrice } from "./Price";

/** "₺40,00 cheaper at Watsons" on the home page. Nothing when no store is cheaper today. */
export function CheaperElsewhere({ note, className }: { note: ElsewhereNote | null; className: string }) {
  if (note === null) return null;
  return (
    <span className={`cheaper-elsewhere ${className}`}>
      <Price value={note.saving} /> cheaper at {note.store_name}
    </span>
  );
}

/** "₺38,89 cheaper", "₺12,00 more" or "same price", compared with this product's size. */
function Comparison({ saving }: { saving: number | null }) {
  if (saving === null) return null;
  if (saving === 0) return <span className="elsewhere__compare">same price</span>;
  return (
    <span className="elsewhere__compare">
      <Price value={Math.abs(saving)} /> {saving > 0 ? "cheaper" : "more"}
    </span>
  );
}

function OfferRow({ offer }: { offer: Offer }) {
  const unlink = useUnlink();
  return (
    <li className="elsewhere__row">
      <Link className="elsewhere__store" to={`/products/${offer.product_id}`}>
        {offer.store_name}
        <span className="visually-hidden">, {offer.name}</span>
      </Link>
      <Price value={offer.price} size="large" />
      <UnitPrice unit={offer.unit_price} />
      <Comparison saving={offer.saving} />
      {!offer.in_stock && <span className="elsewhere__compare">out of stock</span>}
      <button
        type="button"
        className="text-button"
        onClick={() => unlink.mutate(offer.product_id)}
        disabled={unlink.isPending}
      >
        {/* The space stays outside the hidden span: names trim each element's text. */}
        Not the same product <span className="visually-hidden">at {offer.store_name}</span>
      </button>
    </li>
  );
}

/** Pick another tracked product and group it with this one. */
function LinkForm({ product }: { product: ProductDetail }) {
  const { data: products = [] } = useProducts();
  const { data: stores = [] } = useStores();
  const link = useLink();
  const [otherId, setOtherId] = useState("");

  const grouped = new Set(product.elsewhere.map((o) => o.product_id));
  const candidates = products.filter((p) => p.id !== product.id && !grouped.has(p.id));
  if (candidates.length === 0) return null;
  const storeName = (key: string) => stores.find((s) => s.key === key)?.name ?? key;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!otherId) return;
    await link.mutateAsync({ id: product.id, otherId: Number(otherId) });
    setOtherId("");
  }

  return (
    <form className="edit-form" onSubmit={save}>
      <label>
        Same product at
        <select value={otherId} onChange={(e) => setOtherId(e.target.value)}>
          <option value="">choose a product</option>
          {candidates.map((p) => (
            <option key={p.id} value={p.id}>
              {storeName(p.store)}: {p.name}
            </option>
          ))}
        </select>
      </label>
      <button
        className="paper-button paper-button--mustard"
        type="submit"
        disabled={!otherId || link.isPending}
      >
        Link products
      </button>
    </form>
  );
}

/**
 * The same product at other stores, cheapest first, compared at the price you'd pay
 * and per unit, so a bigger bottle compares fairly. Listings are grouped by barcode,
 * or linked by hand here.
 */
export function Elsewhere({ product }: { product: ProductDetail }) {
  return (
    <section className="elsewhere" aria-labelledby="elsewhere-title">
      <h2 id="elsewhere-title" className="elsewhere__title">
        elsewhere
      </h2>
      {product.elsewhere.length > 0 ? (
        <ol className="elsewhere__list">
          {product.elsewhere.map((offer) => (
            <OfferRow key={offer.product_id} offer={offer} />
          ))}
        </ol>
      ) : (
        <p className="elsewhere__empty">Not tracked at another store yet.</p>
      )}
      <LinkForm product={product} />
    </section>
  );
}
