import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import type { Category, Product } from "../api";
import { placement, windowState } from "../scene";
import { Price, UnitPrice } from "./Price";
import { WindowDrawing } from "./WindowDrawing";

interface NightWindowProps {
  product: Product;
  storeName: string;
  room?: Category;
}

/**
 * One product as a window in the building at night.
 *
 * The scatter (tilt, size, nudge, drop) only changes how it looks. In the DOM
 * this is a plain list item with a link, in logical order, so screen reader
 * and keyboard users get a normal list. The window drawing is aria-hidden; the
 * labels carry everything in words.
 */
export function NightWindow({ product, storeName, room }: NightWindowProps) {
  const state = windowState(product, storeName);
  const spot = placement(product.id);
  const s = product.summary;
  const style = {
    "--rotate": `${spot.rotate}deg`,
    "--size": spot.size,
    "--nudge": spot.nudge,
    "--drop": spot.drop,
    "--tape-angle": `${spot.tape}deg`,
  } as CSSProperties;

  return (
    <li className={`spot spot--${state.kind}`} style={style}>
      <Link className="spot__link" to={`/products/${product.id}`}>
        <WindowDrawing
          kind={state.kind}
          photo={{ src: product.image_url, hint: `${room?.name ?? ""} ${product.name}` }}
        />

        <span className="labels">
          <span className="paper paper--taped label label--name">{product.name}</span>
          <span className="paper label label--store">
            {storeName}
            {room && (
              <>
                <span aria-hidden="true"> · </span>
                <span className="visually-hidden">, </span>
                {room.name.toLowerCase()}
              </>
            )}
          </span>
          {state.kind === "blocked" ? (
            <span className="note">{state.words}</span>
          ) : (
            <span className="label label--price">
              {s && <Price value={s.current} size="large" />}
              {s && product.regular_price !== null && (
                <span className="label__card">card price</span>
              )}
              {s && <UnitPrice unit={product.unit_price} className="label__unit" />}
              <span className="label__words">{state.words}</span>
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}
