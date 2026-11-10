import { Link } from "react-router-dom";

import type { Category, Product } from "../api";
import { windowState } from "../scene";
import { PencilCircle, PencilX } from "./Pencil";
import { Price } from "./Price";
import { ProductPhoto } from "./ProductPhoto";

interface QuietItemProps {
  product: Product;
  storeName: string;
  room?: Category;
}

/** One product in quiet mode: a poster line with a cut-out, the facts and a big price. */
export function QuietItem({ product, storeName, room }: QuietItemProps) {
  const state = windowState(product, storeName);
  const s = product.summary;
  const marked = state.kind === "deal" || state.kind === "fake";

  return (
    <li className={`poster-item poster-item--${state.kind}`}>
      <Link className="poster-item__link" to={`/products/${product.id}`}>
        <span className="poster-item__image" aria-hidden="true">
          <ProductPhoto src={product.image_url} hint={`${room?.name ?? ""} ${product.name}`} />
          {state.kind === "fake" && <PencilX />}
        </span>
        <span className="poster-item__text">
          <span className="poster-item__name">{product.name}</span>
          <span className="poster-item__store">
            {storeName}
            {room && `, ${room.name.toLowerCase()}`}
          </span>
          {s && (
            <span className="poster-item__price">
              <Price value={s.current} size="hero" />
              {state.kind === "deal" && <PencilCircle />}
            </span>
          )}
          {s && product.regular_price !== null && (
            <span className="poster-item__card">card price</span>
          )}
          <span className={marked ? "hand-note" : "poster-item__words"}>
            {state.kind === "deal" ? `${state.words}!` : state.kind === "fake" ? "fake sale, skip" : state.words}
          </span>
        </span>
      </Link>
    </li>
  );
}
