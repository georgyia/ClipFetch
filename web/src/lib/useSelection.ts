import { useCallback, useMemo, useState } from "react";

export interface Selection {
  /** Whether the grid is showing checkboxes at all. */
  active: boolean;
  ids: string[];
  count: number;
  has: (id: string) => boolean;
  toggle: (id: string, selected: boolean) => void;
  selectAll: (ids: string[]) => void;
  clear: () => void;
  /** Enter or leave selection mode. Leaving always clears, so nothing acts on a hidden set. */
  setActive: (active: boolean) => void;
}

/**
 * Multi-select state for a clip grid.
 *
 * A Set keyed by clip id rather than by index, because the underlying list grows as pages load —
 * an index-based selection would silently point at different clips after a "Load more".
 *
 * Leaving selection mode clears the set on purpose: a selection you cannot see is a selection you
 * can act on by accident.
 */
export function useSelection(): Selection {
  const [active, setActiveState] = useState(false);
  const [ids, setIds] = useState<Set<string>>(() => new Set());

  const toggle = useCallback((id: string, selected: boolean) => {
    setIds((previous) => {
      const next = new Set(previous);
      if (selected) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback((all: string[]) => {
    setIds(new Set(all));
  }, []);

  const clear = useCallback(() => {
    setIds(new Set());
  }, []);

  const setActive = useCallback((next: boolean) => {
    setActiveState(next);
    if (!next) {
      setIds(new Set());
    }
  }, []);

  return useMemo(
    () => ({
      active,
      ids: Array.from(ids),
      count: ids.size,
      has: (id: string) => ids.has(id),
      toggle,
      selectAll,
      clear,
      setActive,
    }),
    [active, ids, toggle, selectAll, clear, setActive],
  );
}
