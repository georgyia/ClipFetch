import type { UseInfiniteQueryResult } from "@tanstack/react-query";
import type { ClipPage } from "../api/types";
import { Button } from "./Button";
import { ClipGrid } from "./ClipGrid";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";

export interface ClipListViewProps {
  title: string;
  query: UseInfiniteQueryResult<{ pages: ClipPage[] }, unknown>;
  emptyTitle?: string;
  emptyDescription?: string;
}

/** Renders a cursor-paginated clip list with loading/error/empty states and a Load-more control. */
export function ClipListView({ title, query, emptyTitle, emptyDescription }: ClipListViewProps) {
  const { data, isLoading, isError, hasNextPage, isFetchingNextPage, fetchNextPage } = query;

  if (isLoading) {
    return <LoadingState label={`Loading ${title.toLowerCase()}…`} />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Something went wrong"
        description="This view could not be loaded. Try again."
      />
    );
  }

  const items = data.pages.flatMap((page) => page.items);
  if (items.length === 0) {
    return (
      <EmptyState
        title={emptyTitle ?? "Nothing here yet"}
        description={emptyDescription ?? "No clips match this view."}
      />
    );
  }

  const total = data.pages[0]?.total_matched ?? items.length;
  return (
    <div>
      <p aria-live="polite">
        Showing {items.length} of {total}
      </p>
      <ClipGrid items={items} label={title} />
      {hasNextPage ? (
        <div style={{ display: "flex", justifyContent: "center", marginTop: "var(--space-8)" }}>
          <Button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
