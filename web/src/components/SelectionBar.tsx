import { useState } from "react";
import { useToggleFavorite } from "../api/queries";
import type { Selection } from "../lib/useSelection";
import { AddToCollection } from "./AddToCollection";
import { Button } from "./Button";
import styles from "./SelectionBar.module.css";
import { useToast } from "./Toast";
import { Icons } from "./icons";

export interface SelectionBarProps {
  selection: Selection;
  /** Every id currently loaded, for "Select all". */
  allIds: string[];
}

/**
 * Bulk actions over a multi-selection: favorite, and add to a collection.
 *
 * Adding pins the selection into the collection's hand-picked half, so it works on a filtered
 * collection the clips do not match — see AddToCollection.
 */
export function SelectionBar({ selection, allIds }: SelectionBarProps) {
  const toggleFavorite = useToggleFavorite();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);

  if (!selection.active) {
    return null;
  }

  async function favoriteSelected() {
    const ids = selection.ids;
    if (ids.length === 0) {
      return;
    }
    setBusy(true);
    try {
      /*
       * Sequential rather than Promise.all: this is a loopback server with a single SQLite writer,
       * and firing a hundred concurrent writes at it trades a little latency for lock contention.
       */
      for (const clipId of ids) {
        await toggleFavorite.mutateAsync({ clipId, favorite: true });
      }
      toast(`Favorited ${ids.length} clip${ids.length === 1 ? "" : "s"}.`, { variant: "success" });
      selection.clear();
    } catch {
      toast("Could not favorite every clip. Try again.", { variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  const count = selection.count;

  return (
    <div className={styles.bar} role="region" aria-label="Selection actions">
      <p className={styles.count} aria-live="polite">
        {count === 0 ? "Select clips" : `${count} selected`}
      </p>
      <div className={styles.actions}>
        <Button
          size="sm"
          variant="subtle"
          onClick={() => selection.selectAll(allIds)}
          disabled={allIds.length === 0 || count === allIds.length}
        >
          Select all
        </Button>
        <Button size="sm" variant="subtle" onClick={selection.clear} disabled={count === 0}>
          Clear
        </Button>
        <Button
          size="sm"
          variant="subtle"
          icon={Icons.addToCollection}
          disabled={count === 0 || busy}
          onClick={() => setAdding(true)}
        >
          Add to collection
        </Button>
        <Button
          size="sm"
          variant="primary"
          icon={Icons.favorite}
          loading={busy}
          disabled={count === 0}
          onClick={favoriteSelected}
        >
          Favorite
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon={Icons.close}
          onClick={() => selection.setActive(false)}
        >
          Done
        </Button>
      </div>

      {adding ? (
        <AddToCollection
          open
          onClose={() => setAdding(false)}
          clipIds={selection.ids}
          onAdded={selection.clear}
        />
      ) : null}
    </div>
  );
}
