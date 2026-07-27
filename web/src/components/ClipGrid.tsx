import type { ClipSummary } from "../api/types";
import { useRevealOnScroll } from "../lib/useRevealOnScroll";
import { ClipCard } from "./ClipCard";
import styles from "./ClipGrid.module.css";

export interface ClipGridProps {
  items: ClipSummary[];
  label: string;
  progressById?: Record<string, number>;
}

/**
 * How many cards participate in the entrance stagger. Past this point the delay would be long
 * enough to read as "slow loading" rather than as choreography, so the rest simply appear.
 */
const STAGGER_LIMIT = 12;

/** Responsive, density-adaptive grid of clip cards for library, topic, and search views. */
export function ClipGrid({ items, label, progressById }: ClipGridProps) {
  const { ref, revealed } = useRevealOnScroll<HTMLUListElement>();

  return (
    <ul className={styles.grid} aria-label={label} ref={ref} data-revealed={revealed}>
      {items.map((clip, index) => (
        <li
          key={clip.id}
          className={styles.item}
          style={
            index < STAGGER_LIMIT
              ? ({ "--stagger": `${index * 28}ms` } as React.CSSProperties)
              : undefined
          }
        >
          <ClipCard clip={clip} progress={progressById?.[clip.id]} />
        </li>
      ))}
    </ul>
  );
}
