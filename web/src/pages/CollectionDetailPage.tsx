import { useParams } from "react-router-dom";
import { useClipList } from "../api/queries";
import { ClipListView } from "../components/ClipListView";
import { titleize } from "../lib/format";

// A single collection as a browsable channel: the clips its filter currently matches. This is the
// destination for collection rails on Home.
export function CollectionDetailPage() {
  const { id = "" } = useParams();
  const query = useClipList(["collection", id], (cursor) => {
    const params = new URLSearchParams({ limit: "24", sort: "date" });
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/api/v1/collections/${encodeURIComponent(id)}/clips?${params.toString()}`;
  });

  return (
    <section aria-label={titleize(id)}>
      <h1>{titleize(id)}</h1>
      <ClipListView
        title={titleize(id)}
        query={query}
        emptyTitle="No clips match this collection"
        emptyDescription="Adjust the collection's filters to include more clips."
        queueContext={{ from: "collection", key: id }}
      />
    </section>
  );
}
