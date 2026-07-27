import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiGet } from "../api/client";
import type { ClipPage } from "../api/types";
import { Button } from "../components/Button";
import { ClipGrid } from "../components/ClipGrid";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { SkeletonGrid } from "../components/Skeletons";
import { Icons } from "../components/icons";

// The Favorites view: every clip the viewer has favorited in the active library, newest first.
export function FavoritesPage() {
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["favorites"],
    queryFn: () => apiGet<ClipPage>("/api/v1/favorites"),
  });

  if (isLoading) {
    return <SkeletonGrid label="Loading favorites" />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Could not load favorites"
        description="The local server did not answer. Check that it is still running, then retry."
        onRetry={() => refetch()}
        retrying={isFetching}
      />
    );
  }

  return (
    <section aria-label="Favorites">
      <h1>Favorites</h1>
      {data.items.length === 0 ? (
        <EmptyState
          icon={Icons.favorite}
          title="No favorites yet"
          description="Tap the heart on any clip and it will be kept here for quick access."
          action={
            <Link to="/explore">
              <Button variant="primary" icon={Icons.explore}>
                Browse your library
              </Button>
            </Link>
          }
        />
      ) : (
        <ClipGrid items={data.items} label="Favorites" />
      )}
    </section>
  );
}
