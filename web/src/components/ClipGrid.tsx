import type { ClipSummary } from "../api/types";
import { useRevealOnScroll } from "../lib/useRevealOnScroll";
import type { Selection } from "../lib/useSelection";
import { ClipCard } from "./ClipCard";
import styles from "./ClipGrid.module.css";
import { VirtualClipGrid } from "./VirtualClipGrid";

export interface ClipGridProps {
  items: ClipSummary[];
  label: string;
  progressById?: Record<string, number>;
  /** When provided and active, cards show selection checkboxes. */
  selection?: Selection;
}

/**
 * How many cards participate in the entrance stagger. Past this point the delay would be long
 * enough to read as "slow loading" rather than as choreography, so the rest simply appear.
 */
const STAGGER_LIMIT = 12;

/**
 * Above this many items the grid switches to windowed rendering.
 *
 * Below it, measurement and absolute positioning cost more than they save, and the plain grid gets
 * the entrance stagger — which a virtualized grid cannot have, since rows mount and unmount as you
 * scroll and would re-animate every time.
 */
const VIRTUALIZE_ABOVE = 60;

/** Responsive, density-adaptive grid of clip cards for library, topic, and search views. */
export function ClipGrid({ items, label, progressById, selection }: ClipGridProps) {
  const { ref, revealed } = useRevealOnScroll<HTMLUListElement>();

  if (items.length > VIRTUALIZE_ABOVE) {
    return (
      <VirtualClipGrid
        items={items}
        label={label}
        progressById={progressById}
        selection={selection}
      />
    );
  }

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
          <ClipCard
            clip={clip}
            progress={progressById?.[clip.id]}
            selectable={selection?.active}
            selected={selection?.has(clip.id)}
            onSelectChange={(next) => selection?.toggle(clip.id, next)}
          />
        </li>
      ))}
    </ul>
  );
}
