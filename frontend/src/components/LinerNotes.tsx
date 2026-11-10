import { useState } from "react";

import type { Anomaly, PricePoint } from "../api";
import { formatChange, formatDate } from "../format";
import { Price } from "./Price";

const FIRST_LOOK = 24;

/** "A1", "A2" … for the first half of the checks, "B1" … for the second. */
export function trackNumber(index: number, total: number): string {
  const side = Math.ceil(total / 2);
  return index < side ? `A${index + 1}` : `B${index - side + 1}`;
}

/**
 * The price history as liner notes on a record sleeve: every check is a
 * track, oldest first. Long histories show the latest tracks first-look.
 */
export function LinerNotes({ history, anomalies }: { history: PricePoint[]; anomalies: Anomaly[] }) {
  const [all, setAll] = useState(false);
  const unusual = new Set(anomalies.map((a) => a.checked_at));
  const paid = (p: PricePoint) => p.member_price ?? p.price;
  const start = all ? 0 : Math.max(0, history.length - FIRST_LOOK);

  return (
    <section className="sleeve" aria-labelledby="liner-title">
      <div className="sleeve__vinyl" aria-hidden="true" />
      <div className="sleeve__cover">
        <h2 id="liner-title" className="sleeve__title">
          liner notes
        </h2>
        <p className="sleeve__sub">
          Every price check, track by track. {history.length}{" "}
          {history.length === 1 ? "track" : "tracks"}.
        </p>
        {start > 0 && (
          <button type="button" className="text-button sleeve__more" onClick={() => setAll(true)}>
            Show all {history.length} checks
          </button>
        )}
        <ol className="tracks" start={start + 1}>
          {history.slice(start).map((p, i) => {
            const index = start + i;
            const before = index > 0 ? paid(history[index - 1]) : undefined;
            const change = before ? ((paid(p) - before) / before) * 100 : 0;
            return (
              <li key={p.checked_at} className="track">
                <span className="track__no">{trackNumber(index, history.length)}</span>
                <span className="track__date">{formatDate(p.checked_at)}</span>
                <Price value={paid(p)} />
                <span className="track__notes">
                  {Math.abs(change) >= 0.05 && (
                    <span>{change < 0 ? `down ${formatChange(change).slice(1)}` : `up ${formatChange(change).slice(1)}`}</span>
                  )}
                  {p.member_price !== null && (
                    <span>
                      card price, regular <Price value={p.price} />
                    </span>
                  )}
                  {unusual.has(p.checked_at) && <span className="track__flag">unusual rise</span>}
                  {!p.in_stock && <span className="track__flag">out of stock</span>}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
