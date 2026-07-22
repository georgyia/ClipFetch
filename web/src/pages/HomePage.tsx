import { useBootstrap, useHome } from "../api/queries";
import type { ClipSummary, Rail } from "../api/types";
import { ClipRail } from "../components/ClipRail";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Hero } from "../components/Hero";
import { LoadingState } from "../components/LoadingState";

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
        title="No active library"
        description="Register and activate a library to start watching."
      />
    );
  }
  if (home.isLoading || bootstrap.isLoading) {
    return <LoadingState label="Loading your library…" />;
  }
  if (home.isError || !home.data) {
    return (
      <ErrorState
        title="Could not reach the ClipFetch Watch server"
        description="Start the local server, then reload this page."
      />
    );
  }

  const rails = home.data.rails;
  if (rails.length === 0) {
    return (
      <EmptyState
        title="Your library is empty"
        description="Download some clips with the ClipFetch CLI, then reload to see them here."
      />
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
