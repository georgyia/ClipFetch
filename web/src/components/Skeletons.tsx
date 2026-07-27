import { Skeleton } from "./Skeleton";
import styles from "./Skeletons.module.css";

/**
 * Layout-matched loading placeholders.
 *
 * Each skeleton mirrors the real component's box model — the same aspect ratio, gaps, and number
 * of text lines — so when data arrives the content lands exactly where the placeholder was and
 * nothing shifts. That is the whole point: a skeleton that does not match its content is just a
 * more elaborate spinner.
 *
 * Every placeholder is aria-hidden; the wrapper carries a single polite live region instead.
 */

/*
 * Stable keys for placeholder rows. Placeholders are interchangeable, but keying them by array
 * index makes React reconcile them positionally on every count change; a fixed pool of ids keeps
 * each placeholder its own element and keeps the linter honest about index keys.
 */
const PLACEHOLDER_IDS = Array.from({ length: 32 }, (_, index) => `skeleton-${index}`);

function placeholders(count: number): string[] {
  return PLACEHOLDER_IDS.slice(0, count);
}

/**
 * One polite announcement per loading *surface*.
 *
 * An empty label renders nothing at all, which is how composed skeletons stay correct: SkeletonHome
 * announces once and its nested rails stay silent, rather than stacking several live regions that
 * would each fight to speak.
 */
function LoadingRegion({ label }: { label: string }) {
  if (!label) {
    return null;
  }
  return (
    <span role="status" aria-live="polite" className="visually-hidden">
      {label}
    </span>
  );
}

/** Matches ClipCard: a 9:16 poster, then a two-line caption and a short subtitle. */
export function SkeletonCard() {
  return (
    <div className={styles.card} aria-hidden="true">
      <Skeleton className={styles.poster} radius="var(--radius-card)" />
      <Skeleton height="12px" />
      <Skeleton height="12px" width="60%" />
    </div>
  );
}

export interface SkeletonRailProps {
  /** Cards to draw. Roughly a viewport's worth — more would only render off-screen. */
  count?: number;
  label?: string;
}

/** Matches ClipRail: a title row above a horizontally scrolling track of cards. */
export function SkeletonRail({ count = 6, label = "Loading clips" }: SkeletonRailProps) {
  return (
    <section className={styles.rail}>
      <LoadingRegion label={label} />
      <div className={styles.railHeader} aria-hidden="true">
        <Skeleton width="180px" height="20px" />
      </div>
      <div className={styles.railTrack} aria-hidden="true">
        {placeholders(count).map((id) => (
          <div className={styles.railItem} key={id}>
            <SkeletonCard />
          </div>
        ))}
      </div>
    </section>
  );
}

export interface SkeletonGridProps {
  count?: number;
  label?: string;
}

/** Matches ClipGrid, including its responsive column sizing, so the reflow on load is nil. */
export function SkeletonGrid({ count = 12, label = "Loading clips" }: SkeletonGridProps) {
  return (
    <div>
      <LoadingRegion label={label} />
      <div className={styles.grid} aria-hidden="true">
        {placeholders(count).map((id) => (
          <SkeletonCard key={id} />
        ))}
      </div>
    </div>
  );
}

/** Matches Hero: the full-bleed panel with an eyebrow, title, subtitle, and two buttons. */
export function SkeletonHero() {
  return (
    <div className={styles.hero} aria-hidden="true">
      <div className={styles.heroContent}>
        <Skeleton width="120px" height="12px" />
        <Skeleton width="min(420px, 80%)" height="40px" />
        <Skeleton width="min(280px, 60%)" height="16px" />
        <div className={styles.heroActions}>
          <Skeleton width="132px" height="52px" radius="var(--radius-control)" />
          <Skeleton width="132px" height="52px" radius="var(--radius-control)" />
        </div>
      </div>
    </div>
  );
}

/** Home: hero plus the first few rails, which is what the page resolves to. */
export function SkeletonHome() {
  return (
    <div>
      <LoadingRegion label="Loading your library" />
      <SkeletonHero />
      <SkeletonRail label="" />
      <SkeletonRail label="" />
    </div>
  );
}

/** Matches ClipDetailPage: portrait media beside a metadata column. */
export function SkeletonClipDetail() {
  return (
    <div>
      <LoadingRegion label="Loading clip" />
      <div className={styles.detail} aria-hidden="true">
        <Skeleton className={styles.detailMedia} radius="var(--radius-panel)" />
        <div className={styles.detailMeta}>
          <Skeleton width="70%" height="32px" />
          <Skeleton width="40%" height="16px" />
          <div className={styles.detailChips}>
            <Skeleton width="88px" height="28px" radius="var(--radius-pill)" />
            <Skeleton width="72px" height="28px" radius="var(--radius-pill)" />
            <Skeleton width="96px" height="28px" radius="var(--radius-pill)" />
          </div>
          <Skeleton height="14px" />
          <Skeleton height="14px" />
          <Skeleton width="80%" height="14px" />
        </div>
      </div>
    </div>
  );
}

export interface SkeletonListProps {
  rows?: number;
  label?: string;
}

/** Matches the row lists on Library, Downloads, and Collections. */
export function SkeletonList({ rows = 4, label = "Loading" }: SkeletonListProps) {
  return (
    <div>
      <LoadingRegion label={label} />
      <div className={styles.list} aria-hidden="true">
        {placeholders(rows).map((id) => (
          <div className={styles.listRow} key={id}>
            <Skeleton width="40%" height="16px" />
            <Skeleton width="24%" height="12px" />
          </div>
        ))}
      </div>
    </div>
  );
}
