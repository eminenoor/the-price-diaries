/** Red grease-pencil marks for quiet mode. Decorative: the words are always written too. */

export function PencilCircle() {
  return (
    <svg className="pencil pencil--circle" viewBox="0 0 200 100" preserveAspectRatio="none" aria-hidden="true">
      <path d="M38 14C78 2 168 4 188 36c16 27-34 56-96 58C36 96 6 78 10 52 14 26 62 12 112 10c22-1 44 2 58 8" />
    </svg>
  );
}

export function PencilX() {
  return (
    <svg className="pencil pencil--x" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d="M12 10c26 24 52 52 78 82M88 8C62 34 36 62 9 90" />
    </svg>
  );
}
