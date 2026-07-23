import type { UseInfiniteQueryResult } from "@tanstack/react-query";
import type { ClipPage } from "../api/types";
import type { QueueContext } from "../lib/queueSource";
import { Button } from "./Button";
import { ClipGrid } from "./ClipGrid";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { PlayAll } from "./PlayAll";

export interface ClipListViewProps {
  title: string;
  query: UseInfiniteQueryResult<{ pages: ClipPage[] }, unknown>;
  emptyTitle?: string;
  emptyDescription?: string;
  /** When set, a Play-all/Shuffle control opens the player with this list as the queue. */
  queueContext?: QueueContext;
}

/** Renders a cursor-paginated clip list with loading/error/empty states and a Load-more control. */
export function ClipListView({
  title,
  query,
  emptyTitle,
  emptyDescription,
  queueContext,
}: ClipListViewProps) {
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
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          flexWrap: "wrap",
        }}
      >
        <p aria-live="polite">
          Showing {items.length} of {total}
        </p>
        {queueContext ? <PlayAll items={items} context={queueContext} /> : null}
      </div>
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
