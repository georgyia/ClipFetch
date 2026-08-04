import { useParams } from "react-router-dom";
import { useClipList, useCollection, useRemoveClipFromCollection } from "../api/queries";
import { Button } from "../components/Button";
import { ClipListView } from "../components/ClipListView";
import { useToast } from "../components/Toast";
import { Icons } from "../components/icons";
import { titleize } from "../lib/format";

// A single collection as a browsable channel: the clips its filter matches plus the ones pinned
// into it by hand. Pinned clips carry an unpin control, since they are the only ones this page can
// remove — a filter match leaves when the filter stops matching it, not by a click here.
export function CollectionDetailPage() {
  const { id = "" } = useParams();
  const collection = useCollection(id);
  const removeClip = useRemoveClipFromCollection();
  const toast = useToast();
  const query = useClipList(["collection", id], (cursor) => {
    const params = new URLSearchParams({ limit: "24", sort: "date" });
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/api/v1/collections/${encodeURIComponent(id)}/clips?${params.toString()}`;
  });

  const pinned = new Set(collection.data?.pinned ?? []);
  const isManual = collection.data ? collection.data.filters === null : false;

  async function unpin(clipId: string) {
    try {
      await removeClip.mutateAsync({ id, clipId });
      toast(`Removed from ${id}.`, { variant: "success" });
    } catch {
      toast("Could not remove that clip. Try again.", { variant: "error" });
    }
  }

  return (
    <section aria-label={titleize(id)}>
      <h1>{titleize(id)}</h1>
      <ClipListView
        title={titleize(id)}
        query={query}
        emptyTitle="No clips in this collection yet"
        emptyDescription={
          isManual
            ? "This collection has no filter — add clips to it from any grid with Select, or from a card."
            : "Adjust the collection's filters, or add clips to it directly from any grid."
        }
        queueContext={{ from: "collection", key: id }}
        cardAction={(clip) =>
          pinned.has(clip.id) ? (
            <Button
              variant="subtle"
              size="sm"
              iconOnly
              icon={Icons.close}
              aria-label={`Remove from ${id}`}
              disabled={removeClip.isPending}
              onClick={() => unpin(clip.id)}
            />
          ) : null
        }
      />
    </section>
  );
}
