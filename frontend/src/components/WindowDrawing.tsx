import { lighting, type WindowKind } from "../scene";
import { ProductPhoto } from "./ProductPhoto";

interface WindowDrawingProps {
  /** Decides the light, the curtains and the blinds (see lighting() in scene.ts). */
  kind: WindowKind;
  photo?: { src: string | null; hint: string };
  big?: boolean;
}

/**
 * A window with velvet curtains, drawn the same way on every page so the light
 * always follows the status. Decorative: the status is written next to it.
 */
export function WindowDrawing({ kind, photo, big = false }: WindowDrawingProps) {
  const { light, curtains, blinds } = lighting(kind);
  return (
    <span
      className={`window window--${light} curtains--${curtains}${big ? " window--big" : ""}`}
      aria-hidden="true"
    >
      <span className="window__glass">
        {photo && <ProductPhoto src={photo.src} hint={photo.hint} className="window__photo" />}
      </span>
      <span className="curtain curtain--left" />
      <span className="curtain curtain--right" />
      {blinds && <span className="blinds" />}
    </span>
  );
}
