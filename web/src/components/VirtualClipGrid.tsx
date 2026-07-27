import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";
import type { ClipSummary } from "../api/types";
import type { Selection } from "../lib/useSelection";
import { ClipCard } from "./ClipCard";
import styles from "./ClipGrid.module.css";

export interface VirtualClipGridProps {
  items: ClipSummary[];
  label: string;
  progressById?: Record<string, number>;
  selection?: Selection;
}

/*
 * These must stay in step with ClipGrid.module.css. The virtualizer has to know the column
 * geometry to compute row heights, and CSS is the source of truth for the layout itself, so the
 * numbers are duplicated here rather than derived — with a test asserting they still agree.
 */
export const GRID_MIN_COLUMN = { narrow: 140, wide: 168 };
export const GRID_GAP = { narrow: 16, wide: 20 };
export const GRID_WIDE_BREAKPOINT = 768;
/** Caption (2 lines) + subtitle + the gaps between them, from ClipCard's meta block. */
const META_HEIGHT = 52;

/** How many rows to render beyond the viewport, so fast scrolling does not reveal blank space. */
const OVERSCAN = 3;

export interface GridGeometry {
  columns: number;
  gap: number;
  rowHeight: number;
}

/** Resolve the column count and row height a container width implies, mirroring the CSS grid. */
export function gridGeometry(containerWidth: number, viewportWidth: number): GridGeometry {
  const wide = viewportWidth >= GRID_WIDE_BREAKPOINT;
  const minColumn = wide ? GRID_MIN_COLUMN.wide : GRID_MIN_COLUMN.narrow;
  const gap = wide ? GRID_GAP.wide : GRID_GAP.narrow;

  // The inverse of repeat(auto-fill, minmax(min, 1fr)): how many min-width tracks plus gaps fit.
  const columns = Math.max(1, Math.floor((containerWidth + gap) / (minColumn + gap)));
  const columnWidth = (containerWidth - gap * (columns - 1)) / columns;
  // Cards are 9:16 posters plus a fixed meta block.
  const rowHeight = columnWidth * (16 / 9) + META_HEIGHT + gap;

  return { columns, gap, rowHeight };
}

/**
 * A windowed clip grid for large result sets: only the rows near the viewport exist in the DOM.
 *
 * ClipCard already sets `content-visibility: auto`, which lets the browser skip *layout and paint*
 * for off-screen cards — but every card is still a React element and a DOM subtree. At a few
 * thousand clips that node count is what costs, so above a threshold the grid switches to this
 * component and the count stops growing with the library.
 *
 * It virtualizes against the window rather than an inner scroll container, so the page keeps one
 * scrollbar and the browser's own scroll restoration keeps working.
 */
export function VirtualClipGrid({ items, label, progressById, selection }: VirtualClipGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [geometry, setGeometry] = useState<GridGeometry>({
    columns: 1,
    gap: GRID_GAP.narrow,
    rowHeight: 320,
  });

  // Re-measure on resize; the column count and therefore the row height both depend on width.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const measure = () => {
      const width = element.clientWidth;
      if (width > 0) {
        setGeometry(gridGeometry(width, window.innerWidth));
      }
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const rowCount = Math.ceil(items.length / geometry.columns);
  const virtualizer = useWindowVirtualizer({
    count: rowCount,
    estimateSize: () => geometry.rowHeight,
    overscan: OVERSCAN,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  const virtualRows = virtualizer.getVirtualItems();

  return (
    <div ref={containerRef}>
      {/*
        A list rather than the CSS grid: rows are absolutely positioned by the virtualizer, so the
        outer element only provides the total scroll height and each row lays its own columns out.
      */}
      <ul
        className={styles.virtualBody}
        aria-label={label}
        style={{ height: `${virtualizer.getTotalSize()}px` }}
      >
        {virtualRows.map((virtualRow) => {
          const start = virtualRow.index * geometry.columns;
          const rowItems = items.slice(start, start + geometry.columns);
          return (
            <li
              key={virtualRow.key}
              className={styles.virtualRow}
              style={{
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start - virtualizer.options.scrollMargin}px)`,
                gridTemplateColumns: `repeat(${geometry.columns}, 1fr)`,
                gap: `${geometry.gap}px`,
              }}
            >
              {rowItems.map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  progress={progressById?.[clip.id]}
                  selectable={selection?.active}
                  selected={selection?.has(clip.id)}
                  onSelectChange={(next) => selection?.toggle(clip.id, next)}
                />
              ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
