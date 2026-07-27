import { Link } from "react-router-dom";
import { useBootstrap, useHome } from "../api/queries";
import type { ClipSummary, Rail } from "../api/types";
import { Button } from "../components/Button";
import { ClipRail } from "../components/ClipRail";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Hero } from "../components/Hero";
import { SkeletonHome } from "../components/Skeletons";
import { Icons } from "../components/icons";

function pickFeatured(rails: Rail[]): ClipSummary | null {
  for (const rail of rails) {
    const available = rail.items.find((clip) => clip.available);
    if (available) {
      return available;
    }
  }
  return rails[0]?.items[0] ?? null;
}

// Home: a featured hero over the composed, server-ordered rails (Continue Watching, Recently
// Added, Favorites, then topics and collections). Empty and error states are explicit.
export function HomePage() {
  const bootstrap = useBootstrap();
  const home = useHome();

  if (bootstrap.data && !bootstrap.data.active_library) {
    return (
      <EmptyState
        icon={Icons.library}
        title="No active library"
        description="Register a folder of clips and activate it — Watch reads from a library on this machine."
        action={
          <Link to="/library">
            <Button variant="primary" icon={Icons.folderOpen}>
              Add a library
            </Button>
          </Link>
        }
      />
    );
  }
  if (home.isLoading || bootstrap.isLoading) {
    // A layout-matched skeleton rather than a spinner, so nothing shifts when the rails arrive.
    return <SkeletonHome />;
  }
  if (home.isError || !home.data) {
    return (
      <ErrorState
        title="Could not reach the ClipFetch Watch server"
        description="The local server may have stopped. Start it again, then retry."
        onRetry={() => home.refetch()}
        retrying={home.isFetching}
      />
    );
  }

  const rails = home.data.rails;
  if (rails.length === 0) {
    return (
      <EmptyState
        icon={Icons.downloads}
        title="Your library is empty"
        description="Download clips with the ClipFetch CLI, or queue them from Downloads — they'll show up here as rails."
        action={
          <Link to="/downloads">
            <Button variant="primary" icon={Icons.downloads}>
              Add reels
            </Button>
          </Link>
        }
      >
        <p>
          Already downloaded some? <Link to="/library">Rescan your library</Link> to pick them up.
        </p>
      </EmptyState>
    );
  }

  const featured = pickFeatured(rails);
  return (
    <div>
      {featured ? <Hero clip={featured} /> : null}
      {rails.map((rail) => (
        <ClipRail key={rail.id} title={rail.title} items={rail.items} seeAllTo={rail.destination} />
      ))}
    </div>
  );
}
