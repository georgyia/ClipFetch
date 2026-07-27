import { Link } from "react-router-dom";
import { useClipList } from "../api/queries";
import { Button } from "../components/Button";
import { ClipListView } from "../components/ClipListView";
import { Icons } from "../components/icons";

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
        emptyIcon={Icons.downloads}
        emptyTitle="Your library is empty"
        emptyDescription="Queue a download and the newest clips will land here first."
        emptyAction={
          <Link to="/downloads">
            <Button variant="primary" icon={Icons.downloads}>
              Add reels
            </Button>
          </Link>
        }
        queueContext={{ from: "recent" }}
      />
    </section>
  );
}
