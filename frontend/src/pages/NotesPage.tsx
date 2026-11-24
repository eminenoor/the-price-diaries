import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import type { Note } from "../api";
import { Price } from "../components/Price";
import { formatDate, formatTime, formatWeek } from "../format";
import { useNotes, useReadAllNotes, useReadNote } from "../hooks";
import { useMode } from "../mode";
import { NOTE_LABELS, noteTone, placement } from "../scene";

/** The inbox: notes pinned on the door, newest first. */
export function NotesPage() {
  const { data, isLoading, error } = useNotes();
  const readAll = useReadAllNotes();

  if (isLoading) return <p className="status">Looking for notes…</p>;
  if (error || !data) return <p className="status status--error">The notes couldn't be loaded.</p>;

  return (
    <section className="notes" aria-labelledby="notes-title">
      <h1 id="notes-title" className="notes__title">
        notes on the door
      </h1>
      {data.notes.length === 0 ? (
        <p className="notes__empty">
          No notes yet. After each check, anything worth knowing about your prices is pinned here.
        </p>
      ) : (
        <>
          <div className="notes__summary">
            <p role="status">
              {data.unread === 0
                ? "All notes read."
                : data.unread === 1
                  ? "1 new note."
                  : `${data.unread} new notes.`}
            </p>
            {data.unread > 0 && (
              <button
                type="button"
                className="paper-button"
                onClick={() => readAll.mutate()}
                disabled={readAll.isPending}
              >
                Mark all as read
              </button>
            )}
          </div>
          <ol className="notes__list">
            {data.notes.map((note) => (
              <NoteItem key={note.id} note={note} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function NoteItem({ note }: { note: Note }) {
  const read = useReadNote();
  const { mode } = useMode();
  const style = mode === "night" ? ({ "--tilt": `${placement(note.id).rotate}deg` } as CSSProperties) : undefined;
  const when = new Date(note.created_at);

  return (
    <li className={`inbox-note inbox-note--${note.read ? "read" : "new"} paper paper--taped`} style={style}>
      <p className="inbox-note__head">
        <span className={`inbox-note__label inbox-note__label--${noteTone(note.kind)}`}>{NOTE_LABELS[note.kind]}</span>{" "}
        <span className="inbox-note__status">{note.read ? "read" : "new"}</span>
      </p>
      <p className="inbox-note__text">
        <NoteSentence note={note} />
      </p>
      <p className="inbox-note__foot">
        <time dateTime={note.created_at}>
          {formatDate(note.created_at)}, {formatTime(when)}
        </time>{" "}
        {!note.read && (
          <button
            type="button"
            className="text-button"
            onClick={() => read.mutate(note.id)}
            disabled={read.isPending}
          >
            Mark as read
          </button>
        )}
      </p>
    </li>
  );
}

/** The note in one plain sentence, the same one the desktop notification shows. */
function NoteSentence({ note }: { note: Note }) {
  if (note.kind === "sunday_paper") {
    const week = note.week ?? "";
    return (
      <>
        <Link to={`/paper?week=${week}`}>Your Sunday paper is ready</Link>: the week of {formatWeek(week)}, on one
        page.
      </>
    );
  }
  const name = <Link to={`/products/${note.product_id}`}>{note.product_name}</Link>;
  const now = note.new_price !== null ? <Price value={note.new_price} /> : null;
  // "(was ₺420,00)" next to "now ₺420,00" says nothing, so leave it out.
  const was =
    note.old_price !== null && note.old_price !== note.new_price ? (
      <>
        {" "}
        (was <Price value={note.old_price} />)
      </>
    ) : null;

  switch (note.kind) {
    case "target":
      return (
        <>
          {name} at {note.store_name} is now {now}
          {was}, at or under your alert price.
        </>
      );
    case "lowest":
      return (
        <>
          {name} at {note.store_name} is now {now}
          {was}, the lowest since you started tracking.
        </>
      );
    case "fake_sale":
      return (
        <>
          {name} at {note.store_name} is now {now}
          {was}, but only after a recent price rise. Not really cheaper.
        </>
      );
    case "cheaper":
      return (
        <>
          {name} is {now} at {note.other_store_name} for the same amount,{" "}
          {note.old_price !== null && <Price value={note.old_price} />} at {note.store_name}.
        </>
      );
    case "back_in_stock":
      return (
        <>
          {name} is back in stock at {note.store_name}, now {now}
          {was}.
        </>
      );
  }
}
