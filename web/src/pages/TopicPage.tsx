import { Link, useParams } from "react-router-dom";
import { useClipList } from "../api/queries";
import { Button } from "../components/Button";
import { ClipListView } from "../components/ClipListView";
import { Icons } from "../components/icons";
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
        emptyIcon={Icons.topics}
        emptyTitle="No clips in this topic"
        emptyDescription="Topics are derived from captions and hashtags as clips are catalogued."
        emptyAction={
          <Link to="/explore">
            <Button variant="primary" icon={Icons.explore}>
              Explore other topics
            </Button>
          </Link>
        }
        queueContext={{ from: "topic", key: slug }}
      />
    </section>
  );
}
