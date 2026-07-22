import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ClipPage } from "../api/types";
import { ClipGrid } from "../components/ClipGrid";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

// The Favorites view: every clip the viewer has favorited in the active library, newest first.
export function FavoritesPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["favorites"],
    queryFn: () => apiGet<ClipPage>("/api/v1/favorites"),
  });

  if (isLoading) {
    return <LoadingState label="Loading favorites…" />;
  }
  if (isError || !data) {
    return <ErrorState title="Something went wrong" description="Favorites could not be loaded." />;
  }

  return (
    <section aria-label="Favorites">
      <h1>Favorites</h1>
      {data.items.length === 0 ? (
        <EmptyState
          title="No favorites yet"
          description="Tap the heart on any clip to keep it here."
        />
      ) : (
        <ClipGrid items={data.items} label="Favorites" />
      )}
    </section>
  );
}
