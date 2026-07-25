import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { ClipSummary } from "../api/types";
import { ClipCard } from "./ClipCard";
import styles from "./ClipRail.module.css";

export interface ClipRailProps {
  title: string;
  items: ClipSummary[];
  /** Route for the rail's "See all" link and destination. */
  seeAllTo?: string;
  /** Optional per-clip playback progress (0–1), keyed by clip id. */
  progressById?: Record<string, number>;
}

/**
 * Horizontal, keyboard-navigable row of clip cards with Netflix-style paging: hover chevrons scroll
 * a page at a time and edge fades hint at more, fading out at each end. Arrow keys move focus
 * between cards for keyboard users.
 */
export function ClipRail({ title, items, seeAllTo, progressById }: ClipRailProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  const syncEdges = useCallback(() => {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    const max = track.scrollWidth - track.clientWidth;
    setCanLeft(track.scrollLeft > 4);
    setCanRight(track.scrollLeft < max - 4);
  }, []);

  useEffect(() => {
    syncEdges();
    window.addEventListener("resize", syncEdges);
    return () => window.removeEventListener("resize", syncEdges);
  }, [syncEdges]);

  function page(direction: 1 | -1) {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    track.scrollBy({ left: direction * Math.round(track.clientWidth * 0.9), behavior: "smooth" });
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
      return;
    }
    const track = trackRef.current;
    if (!track) {
      return;
    }
    const links = Array.from(track.querySelectorAll<HTMLAnchorElement>("a[href]"));
    const current = document.activeElement;
    const index = links.findIndex((link) => link === current);
    if (index === -1) {
      return;
    }
    const next = event.key === "ArrowRight" ? index + 1 : index - 1;
    if (next >= 0 && next < links.length) {
      event.preventDefault();
      links[next].focus();
      links[next].scrollIntoView({ block: "nearest", inline: "center" });
    }
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <section className={styles.rail} aria-label={title}>
      <div className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
        {seeAllTo ? (
          <Link className={styles.seeAll} to={seeAllTo}>
            See all →
          </Link>
        ) : null}
      </div>
      <div className={styles.viewport}>
        <button
          type="button"
          className={`${styles.chevron} ${styles.chevronLeft}`}
          data-visible={canLeft}
          aria-label={`Scroll ${title} backward`}
          tabIndex={-1}
          onClick={() => page(-1)}
        >
          ‹
        </button>
        <div
          className={styles.track}
          ref={trackRef}
          onKeyDown={onKeyDown}
          onScroll={syncEdges}
          role="list"
        >
          {items.map((clip) => (
            <div role="listitem" key={clip.id}>
              <ClipCard clip={clip} progress={progressById?.[clip.id]} />
            </div>
          ))}
        </div>
        <button
          type="button"
          className={`${styles.chevron} ${styles.chevronRight}`}
          data-visible={canRight}
          aria-label={`Scroll ${title} forward`}
          tabIndex={-1}
          onClick={() => page(1)}
        >
          ›
        </button>
      </div>
    </section>
  );
}
