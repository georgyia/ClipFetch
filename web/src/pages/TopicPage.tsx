import { useParams } from "react-router-dom";
import { useClipList } from "../api/queries";
import { ClipListView } from "../components/ClipListView";
import { titleize } from "../lib/format";

// A single topic as a browsable channel: a paginated grid of its clips.
export function TopicPage() {
  const { slug = "" } = useParams();
  const query = useClipList(["topic", slug], (cursor) => {
    const params = new URLSearchParams({ limit: "24", sort: "date" });
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/api/v1/topics/${encodeURIComponent(slug)}/clips?${params.toString()}`;
  });

  return (
    <section aria-label={titleize(slug)}>
      <h1>{titleize(slug)}</h1>
      <ClipListView
        title={titleize(slug)}
        query={query}
        emptyTitle="No clips in this topic"
        emptyDescription="Clips tagged with this topic will appear here."
      />
    </section>
  );
}
