import { type FormEvent, useState } from "react";
import { ApiError } from "../api/client";
import { useAddClipsToCollection, useCollections, useCreateCollection } from "../api/queries";
import type { CollectionSummary } from "../api/types";
import styles from "./AddToCollection.module.css";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Icon } from "./Icon";
import { SkeletonList } from "./Skeletons";
import { useToast } from "./Toast";
import { Icons } from "./icons";

export interface AddToCollectionProps {
  open: boolean;
  onClose: () => void;
  /** The clips to pin. One from a card, many from a grid selection. */
  clipIds: string[];
  /** Called once clips were pinned, so a selection can clear itself. */
  onAdded?: () => void;
}

function plural(count: number) {
  return `${count} clip${count === 1 ? "" : "s"}`;
}

/** True when every clip being added is already pinned into this collection. */
function alreadyHolds(collection: CollectionSummary, clipIds: string[]) {
  const pinned = new Set(collection.pinned);
  return clipIds.length > 0 && clipIds.every((id) => pinned.has(id));
}

/**
 * Pin one clip or a whole selection into a collection.
 *
 * Collections are part filter, part hand-picked: this dialog only ever touches the hand-picked
 * half, which is why a clip can be added to a filtered collection it does not match. Rows that
 * already hold every selected clip say so instead of offering a no-op.
 *
 * "New collection" creates one with *no* filter, so it starts as exactly what was added and does
 * not silently grow later.
 */
export function AddToCollection({ open, onClose, clipIds, onAdded }: AddToCollectionProps) {
  // Only fetch once the dialog is open: this mounts under every card in a grid.
  const collections = useCollections(open);
  const addClips = useAddClipsToCollection();
  const create = useCreateCollection();
  const toast = useToast();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  function finish(collectionId: string) {
    toast(`Added ${plural(clipIds.length)} to ${collectionId}.`, { variant: "success" });
    onAdded?.();
    onClose();
  }

  function fail(err: unknown, fallback: string) {
    setError(err instanceof ApiError ? err.message : fallback);
  }

  async function addTo(collectionId: string) {
    setError("");
    setBusy(collectionId);
    try {
      await addClips.mutateAsync({ id: collectionId, clipIds });
      finish(collectionId);
    } catch (err) {
      fail(err, "Could not add to that collection.");
    } finally {
      setBusy(null);
    }
  }

  async function createAndAdd(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy("__new__");
    try {
      const created = await create.mutateAsync({ name, filters: null, clips: clipIds });
      setName("");
      finish(created.id);
    } catch (err) {
      fail(err, "Could not create the collection.");
    } finally {
      setBusy(null);
    }
  }

  const items = collections.data?.collections ?? [];

  return (
    <Dialog open={open} onClose={onClose} title={`Add ${plural(clipIds.length)} to a collection`}>
      {collections.isLoading ? <SkeletonList label="Loading collections" /> : null}

      {collections.isError ? (
        <p className={styles.error} role="alert">
          Could not load your collections.
        </p>
      ) : null}

      {!collections.isLoading && !collections.isError && items.length === 0 ? (
        <p className={styles.hint}>No collections yet — name one below to start.</p>
      ) : null}

      {items.length > 0 ? (
        <ul className={styles.list}>
          {items.map((collection) => {
            const holds = alreadyHolds(collection, clipIds);
            return (
              <li key={collection.id} className={styles.item}>
                <span className={styles.name}>
                  <Icon icon={collection.filters ? Icons.filter : Icons.collections} size="sm" />
                  {collection.id}
                </span>
                <span className={styles.count}>{collection.clip_count}</span>
                <Button
                  size="sm"
                  variant={holds ? "ghost" : "subtle"}
                  icon={holds ? Icons.confirm : Icons.add}
                  disabled={holds || busy !== null}
                  loading={busy === collection.id}
                  onClick={() => addTo(collection.id)}
                >
                  {holds ? "Added" : "Add"}
                </Button>
              </li>
            );
          })}
        </ul>
      ) : null}

      <form className={styles.form} onSubmit={createAndAdd}>
        <label className={styles.label} htmlFor="new-collection-name">
          New collection
        </label>
        <div className={styles.row}>
          <input
            id="new-collection-name"
            className={styles.control}
            value={name}
            placeholder="e.g. keepers"
            onChange={(event) => setName(event.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            icon={Icons.addToCollection}
            disabled={!name || busy !== null}
            loading={busy === "__new__"}
          >
            Create
          </Button>
        </div>
        <p className={styles.hint}>Lowercase letters, numbers, and single hyphens.</p>
      </form>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      <div className={styles.actions}>
        <Button variant="ghost" onClick={onClose}>
          Done
        </Button>
      </div>
    </Dialog>
  );
}
