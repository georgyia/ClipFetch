import styles from "./SkeletonCard.module.css";

// Purely decorative loading placeholder. Hidden from assistive tech; a sibling live region should
// announce loading. The pulse animation is disabled under prefers-reduced-motion (see tokens.css).
export function SkeletonCard() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={`${styles.poster} ${styles.pulse}`} />
      <div className={`${styles.line} ${styles.pulse}`} />
      <div className={`${styles.line} ${styles.short} ${styles.pulse}`} />
    </div>
  );
}
