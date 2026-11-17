import type { CSSProperties, ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type {
  Paper,
  PaperCheaper,
  PaperFakeSale,
  PaperItem,
  PaperLow,
  PaperMove,
  PaperTrouble,
} from "../api";
import { Price } from "../components/Price";
import { formatDate, formatWeek } from "../format";
import { usePaper } from "../hooks";
import { useMode } from "../mode";
import {
  PRINT_LIMIT,
  type PaperSection,
  checkedLine,
  moveWords,
  paperLead,
  paperSections,
  placement,
  quietWeekLine,
} from "../scene";

/**
 * The Sunday paper: one week on one page, like a printed weekend paper. At night it's a
 * sheet of newsprint taped up in the dark; in quiet mode, a plain poster. Either way it
 * prints on one A4 page.
 */
export function PaperPage() {
  const [params] = useSearchParams();
  const week = params.get("week");
  const { data, isLoading, error } = usePaper(week);

  if (isLoading) return <p className="status">Fetching the paper…</p>;
  if (error || !data)
    return (
      <p className="status status--error">
        {error?.message ?? "The paper couldn't be loaded."} <Link to="/paper">Read the latest paper</Link>
      </p>
    );
  return <Edition paper={data} />;
}

function Edition({ paper }: { paper: Paper }) {
  const { mode } = useMode();
  // A small tilt for the whole sheet at night, the same every time for the same week.
  const tilt = placement(Number(paper.week_start.replaceAll("-", ""))).rotate / 3;
  const style = mode === "night" ? ({ "--tilt": `${tilt}deg` } as CSSProperties) : undefined;
  const lead = paperLead(paper);
  const quiet = quietWeekLine(paper);

  return (
    <>
      <article className="sunday-paper paper paper--taped" style={style} aria-labelledby="paper-title">
        <header className="sunday-paper__masthead">
          <h1 id="paper-title" className="sunday-paper__title">
            <span className="sunday-paper__the">the</span> sunday paper
          </h1>
          <p className="sunday-paper__dateline">
            <span>
              The week of{" "}
              <time dateTime={paper.week_start}>{formatWeek(paper.week_start, true)}</time>
            </span>
            <span>{checkedLine(paper.products_checked)}</span>
          </p>
        </header>

        {quiet ? (
          <p className="sunday-paper__quiet">{quiet}</p>
        ) : (
          <>
            {lead && <Lead move={lead} />}
            <div className="sunday-paper__columns">
              {paperSections(paper).map((section) => (
                <Section key={section.key} section={section} paper={paper} />
              ))}
            </div>
          </>
        )}
      </article>

      <nav className="paper-nav" aria-label="Other weeks">
        {paper.previous_week ? (
          <Link className="paper-button" to={`/paper?week=${paper.previous_week}`}>
            Previous week
          </Link>
        ) : (
          <span />
        )}
        <button type="button" className="text-button" onClick={() => window.print()}>
          Print this page
        </button>
        {paper.next_week ? (
          <Link className="paper-button" to={`/paper?week=${paper.next_week}`}>
            Next week
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </>
  );
}

/** The biggest drop of the week, set as the front-page headline. */
function Lead({ move }: { move: PaperMove }) {
  return (
    <section className="paper-lead" aria-labelledby="paper-lead-title">
      <p className="paper-lead__kicker">biggest drop</p>
      <h2 id="paper-lead-title" className="paper-lead__headline">
        <Link to={`/products/${move.product_id}`}>{move.name}</Link> {moveWords(move.change_pct)}
      </h2>
      <p className="paper-lead__prices">
        <Price value={move.new_price} size="large" /> at {move.store_name}, was <Price value={move.old_price} />
      </p>
      <p className="paper-hand paper-lead__hand" aria-hidden="true">
        the deal of the week!
      </p>
    </section>
  );
}

function Section({ section, paper }: { section: PaperSection; paper: Paper }) {
  const id = `paper-${section.key}`;
  const items = itemsOf(section, paper);
  const more = section.count - section.printed;
  return (
    <section className={`paper-section paper-section--${section.tone}`} aria-labelledby={id}>
      <h2 id={id} className="paper-section__title">
        <span>{section.title}</span>
      </h2>
      {section.hand && (
        <p className="paper-hand" aria-hidden="true">
          {section.hand}
        </p>
      )}
      <ol className="paper-list">
        {items.map((item, i) => (
          <li key={item.key} className={i >= PRINT_LIMIT ? "paper-list__extra" : undefined}>
            {item.line}
          </li>
        ))}
      </ol>
      {more > 0 && (
        <p className="paper-list__more" aria-hidden="true">
          and {more} more
        </p>
      )}
    </section>
  );
}

function itemsOf(section: PaperSection, paper: Paper): { key: string; line: ReactNode }[] {
  const line = <T extends PaperItem>(items: T[], write: (item: T) => ReactNode) =>
    items.map((item) => ({ key: `${section.key}-${item.product_id}`, line: write(item) }));
  switch (section.key) {
    case "drops":
      return line(paper.drops.slice(1), (m) => <MoveLine move={m} />);
    case "rises":
      return line(paper.rises, (m) => <MoveLine move={m} />);
    case "new_lows":
      return line(paper.new_lows, (low) => <LowLine low={low} />);
    case "fake_sales":
      return line(paper.fake_sales, (fake) => <FakeLine fake={fake} />);
    case "cheaper":
      return line(paper.cheaper, (c) => <CheaperLine cheaper={c} />);
    case "trouble":
      return line(paper.trouble, (t) => <TroubleLine trouble={t} />);
  }
}

function Name({ item }: { item: PaperItem }) {
  return <Link to={`/products/${item.product_id}`}>{item.name}</Link>;
}

/** "Serum at Gratis, down 12.0%: ₺400,00 to ₺352,00." */
function MoveLine({ move }: { move: PaperMove }) {
  return (
    <>
      <Name item={move} /> at {move.store_name}, <b>{moveWords(move.change_pct)}</b>: <Price value={move.old_price} />{" "}
      to <Price value={move.new_price} />.
    </>
  );
}

/** "Serum at Gratis: ₺352,00 on 10 Nov, under the old low of ₺380,00." */
function LowLine({ low }: { low: PaperLow }) {
  return (
    <>
      <Name item={low} /> at {low.store_name}: <Price value={low.price} /> on {formatDate(low.at)}, under the old
      low of <Price value={low.previous_low} />.
    </>
  );
}

/** "Sunscreen at Watsons: "on sale" at ₺349,00 on 12 Nov, after a rise to ₺436,25." */
function FakeLine({ fake }: { fake: PaperFakeSale }) {
  return (
    <>
      <Name item={fake} /> at {fake.store_name}: “on sale” at <Price value={fake.price} /> on {formatDate(fake.at)},
      after a rise to <Price value={fake.peak} />.
    </>
  );
}

/** "Toner: ₺340,00 at Watsons, ₺494,00 at Gratis, on 13 Nov." */
function CheaperLine({ cheaper }: { cheaper: PaperCheaper }) {
  return (
    <>
      <Name item={cheaper} />: <Price value={cheaper.price_there} /> at {cheaper.other_store_name},{" "}
      <Price value={cheaper.price_here} /> at {cheaper.store_name}, on {formatDate(cheaper.at)}.
    </>
  );
}

/** "Cream at Sephora: 3 checks failed (www.sephora.com.tr blocks…). Sold out from 13 Nov." */
function TroubleLine({ trouble }: { trouble: PaperTrouble }) {
  const failed =
    trouble.failed_checks === 0
      ? null
      : `${trouble.failed_checks === 1 ? "1 check" : `${trouble.failed_checks} checks`} failed${
          trouble.last_error ? ` (${trouble.last_error.replace(/\.$/, "")})` : ""
        }.`;
  const soldOut = trouble.out_of_stock_at ? `Sold out from ${formatDate(trouble.out_of_stock_at)}.` : null;
  return (
    <>
      <Name item={trouble} /> at {trouble.store_name}: {[failed, soldOut].filter(Boolean).join(" ")}
    </>
  );
}
