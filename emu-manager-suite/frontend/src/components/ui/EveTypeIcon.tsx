"use client";

import { useEffect, useMemo, useState } from "react";
import { isValidEvetechTypeId, typeImageCandidates, type TypeImageMeta } from "@/lib/evetech";

const PLACEHOLDER =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#1a1f26"/><path d="M8 16h16M16 8v16" stroke="#4a5568" stroke-width="2"/></svg>'
  );

const failedUrls = new Set<string>();

type EveTypeIconProps = {
  typeId: number;
  size?: number;
  className?: string;
  categoryName?: string | null;
  groupName?: string | null;
  preferRender?: boolean;
};

/** Type icon with blueprint-aware and render fallbacks. */
export function EveTypeIcon({
  typeId,
  size = 32,
  className,
  categoryName,
  groupName,
  preferRender,
}: EveTypeIconProps) {
  const meta = useMemo<TypeImageMeta>(
    () => ({ categoryName, groupName, preferRender }),
    [categoryName, groupName, preferRender]
  );

  const candidates = useMemo(
    () => typeImageCandidates(typeId, size, meta).filter((url) => !failedUrls.has(url)),
    [typeId, size, meta]
  );

  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
  }, [typeId, categoryName, groupName, preferRender, size]);

  if (!isValidEvetechTypeId(typeId)) {
    return (
      <img
        src={PLACEHOLDER}
        alt=""
        width={size}
        height={size}
        className={className}
        loading="lazy"
        decoding="async"
      />
    );
  }

  const src = index < candidates.length ? candidates[index] : PLACEHOLDER;

  return (
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className={className}
      loading="lazy"
      decoding="async"
      onError={() => {
        const failed = candidates[index];
        if (failed) failedUrls.add(failed);
        setIndex((current) => current + 1);
      }}
    />
  );
}
