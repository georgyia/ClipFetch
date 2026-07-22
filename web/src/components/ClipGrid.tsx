import type { ClipSummary } from "../api/types";
import { ClipCard } from "./ClipCard";
import styles from "./ClipGrid.module.css";

export interface ClipGridProps {
  items: ClipSummary[];
  label: string;
  progressById?: Record<string, number>;
}

/** Responsive, density-adaptive grid of clip cards for library, topic, and search views. */
export function ClipGrid({ items, label, progressById }: ClipGridProps) {
  return (
    <ul className={styles.grid} aria-label={label}>
      {items.map((clip) => (
        <li key={clip.id}>
          <ClipCard clip={clip} progress={progressById?.[clip.id]} />
        </li>
      ))}
    </ul>
  );
}
