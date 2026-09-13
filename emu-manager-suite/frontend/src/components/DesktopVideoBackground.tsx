"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchActiveDesktopBackgrounds,
  type DesktopBackground,
} from "@/lib/desktopBackgrounds";

function pickBackground(
  backgrounds: DesktopBackground[],
  excludeUrls: Set<string>
): DesktopBackground | null {
  const pool = backgrounds.filter((b) => !excludeUrls.has(b.video_url));
  if (pool.length === 0) return null;
  return pool[Math.floor(Math.random() * pool.length)];
}

export function DesktopVideoBackground() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [backgrounds, setBackgrounds] = useState<DesktopBackground[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [failedUrls, setFailedUrls] = useState<Set<string>>(() => new Set());
  const [selected, setSelected] = useState<DesktopBackground | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchActiveDesktopBackgrounds()
      .then((rows) => {
        if (!cancelled) {
          setBackgrounds(rows);
          setSelected(pickBackground(rows, new Set()));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBackgrounds([]);
          setSelected(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const tryNext = useCallback(
    (failedUrl: string) => {
      const remaining = backgrounds.filter(
        (b) => b.video_url !== failedUrl && !failedUrls.has(b.video_url)
      );
      if (remaining.length === 0) return;
      setFailedUrls((prev) => {
        const next = new Set(prev);
        next.add(failedUrl);
        setSelected(pickBackground(backgrounds, next));
        return next;
      });
    },
    [backgrounds, failedUrls]
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !selected) return;

    video.load();
    const play = () => {
      void video.play().catch(() => {
        /* Autoplay may be blocked; keep the element mounted for user gesture / retry */
      });
    };
    video.addEventListener("canplay", play);
    play();
    return () => video.removeEventListener("canplay", play);
  }, [selected]);

  const hasVideo = loaded && selected;

  if (!hasVideo) {
    return <div className="eve-desktop-bg-fallback" aria-hidden />;
  }

  return (
    <div className="eve-desktop-bg" aria-hidden>
      <video
        key={selected.video_url}
        ref={videoRef}
        className="eve-desktop-bg-video"
        src={selected.video_url}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        onError={() => tryNext(selected.video_url)}
      />
      <div className="eve-desktop-bg-scrim" />
    </div>
  );
}
