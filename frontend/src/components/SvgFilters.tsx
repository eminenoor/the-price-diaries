/** SVG filters used from CSS with filter: url(#…). Rendered once, in App. */
export function SvgFilters() {
  return (
    <svg className="visually-hidden" aria-hidden="true" focusable="false">
      {/* DIARIES: shrinks the lit panes a little, so no thin sliver of light shows at a letter's edge. */}
      <filter id="pane-edge">
        <feMorphology in="SourceAlpha" operator="erode" radius="2" result="inside" />
        <feComposite in="SourceGraphic" in2="inside" operator="in" />
      </filter>
      {/* The same for small screens, where the strokes are thin. */}
      <filter id="pane-edge-small">
        <feMorphology in="SourceAlpha" operator="erode" radius="1" result="inside" />
        <feComposite in="SourceGraphic" in2="inside" operator="in" />
      </filter>

      {/*
        Product photos in lit windows: a slight drop shadow like a paper cut-out.
        Store photos are mostly JPEGs on white, so the shadow is cast by every
        pixel that isn't near-pure white (or transparent, like the letterbox
        object-fit leaves), not by the photo's rectangle. With
        mix-blend-mode: multiply the white itself disappears into the light.
      */}
      <filter id="cutout-shadow" x="-10%" y="-10%" width="130%" height="130%">
        <feColorMatrix
          in="SourceGraphic"
          type="matrix"
          values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -20 -20 -20 59.4 0"
          result="shape"
        />
        <feGaussianBlur in="shape" stdDeviation="2.5" result="soft" />
        <feOffset in="soft" dx="4" dy="6" result="moved" />
        <feFlood className="cutout-shadow__colour" />
        <feComposite in2="moved" operator="in" result="shadow" />
        <feMerge>
          <feMergeNode in="shadow" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </svg>
  );
}
