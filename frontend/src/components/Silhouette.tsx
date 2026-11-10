/**
 * A dark cut-out shape standing in for a product photo.
 * The shape is picked from the room and product name.
 */

type Shape = "dropper" | "bottle" | "jar" | "tube" | "pouch" | "jug" | "box" | "pills";

const RULES: [RegExp, Shape][] = [
  [/serum|vitamin c|ampoule|dropper/i, "dropper"],
  [/cream|moisturi[sz]er|balm|jar|butter/i, "jar"],
  [/sun|spf|cleanser|tube|gel|paste/i, "tube"],
  [/coffee|tea|bean|pouch|granola|rice/i, "pouch"],
  [/laundry|detergent|softener|bleach|jug/i, "jug"],
  [/tablet|dishwasher|box|pods/i, "box"],
  [/vitamin|magnesium|zinc|omega|caps|supplement|mineral/i, "pills"],
];

export function shapeFor(text: string): Shape {
  return RULES.find(([pattern]) => pattern.test(text))?.[1] ?? "bottle";
}

const PATHS: Record<Shape, string> = {
  dropper:
    "M44 8h12v14h-12z M41 22h18v10h-18z M30 36q0-4 4-4h32q4 0 4 4v92q0 6-6 6H36q-6 0-6-6z",
  bottle:
    "M42 6h16v16H42z M38 22h24l4 12q8 4 8 14v80q0 6-6 6H32q-6 0-6-6V48q0-10 8-14z",
  jar: "M22 58h56v10H22z M18 68h64v54q0 12-12 12H30q-12 0-12-12z",
  tube: "M30 6h40l-6 92H36z M34 98h32v14H34z M38 112h24v22H38z",
  pouch: "M22 22h56l-4 10 8 96q0 6-6 6H24q-6 0-6-6l8-96z M30 10h40v12H30z",
  jug: "M30 30h30l6-14h12v14l6 12v86q0 6-6 6H30q-6 0-6-6V40q0-10 6-10z M64 50h12v40H64z",
  box: "M14 54l36-14 36 14v74l-36 6-36-6z",
  pills: "M28 40h44v16H28z M30 56h40v72q0 6-6 6H36q-6 0-6-6z",
};

export function Silhouette({ text, className = "" }: { text: string; className?: string }) {
  return (
    <svg
      className={`silhouette ${className}`}
      viewBox="0 0 100 140"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[shapeFor(text)]} fillRule="evenodd" />
    </svg>
  );
}
