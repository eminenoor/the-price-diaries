import { useState } from "react";

import { Silhouette } from "./Silhouette";

interface ProductPhotoProps {
  src: string | null;
  /** Room and product name: picks the silhouette shape when there is no photo. */
  hint: string;
  className?: string;
}

/**
 * The store's product photo as a cut-out, or a silhouette when there is none
 * or it fails to load. Decorative: the product name is always written nearby.
 */
export function ProductPhoto({ src, hint, className = "" }: ProductPhotoProps) {
  const [failed, setFailed] = useState(false);
  if (!src || failed || !src.startsWith("https://"))
    return <Silhouette text={hint} className={className} />;
  return (
    <img
      className={`cutout ${className}`}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
