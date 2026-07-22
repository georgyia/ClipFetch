import { useClipList } from "../api/queries";
import { ClipListView } from "../components/ClipListView";

// "See all" destination for the Recently Added rail: the whole library, newest first.
export function RecentPage() {
  const query = useClipList(["clips", "recent"], (cursor) => {
    const params = new URLSearchParams({ limit: "24", sort: "date" });
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/api/v1/clips?${params.toString()}`;
  });

  return (
    <section aria-label="Recently Added">
      <h1>Recently Added</h1>
      <ClipListView
        title="Recently Added"
        query={query}
        emptyTitle="Your library is empty"
        emptyDescription="Download some clips with the ClipFetch CLI to see them here."
      />
    </section>
  );
}
