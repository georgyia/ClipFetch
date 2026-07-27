import type { UseInfiniteQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ClipPage } from "../api/types";
import type { QueueContext } from "../lib/queueSource";
import { useSelection } from "../lib/useSelection";
import { Button } from "./Button";
import { ClipGrid } from "./ClipGrid";
import styles from "./ClipListView.module.css";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { PlayAll } from "./PlayAll";
import { SelectionBar } from "./SelectionBar";
import { SkeletonGrid } from "./Skeletons";
import { Icons, type LucideIcon } from "./icons";

export interface ClipListViewProps {
  title: string;
  query: UseInfiniteQueryResult<{ pages: ClipPage[] }, unknown>;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
  /** A CTA for the zero-state — the one thing that would fill this view. */
  emptyAction?: ReactNode;
  /** When set, a Play-all/Shuffle control opens the player with this list as the queue. */
  queueContext?: QueueContext;
}

/** Renders a cursor-paginated clip list with loading/error/empty states and a Load-more control. */
export function ClipListView({
  title,
  query,
  emptyTitle,
  emptyDescription,
  emptyIcon,
  emptyAction,
  queueContext,
}: ClipListViewProps) {
  const selection = useSelection();
  const {
    data,
    isLoading,
    isError,
    isFetching,
    refetch,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = query;

  if (isLoading) {
    return <SkeletonGrid label={`Loading ${title.toLowerCase()}`} />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Something went wrong"
        description="This view could not be loaded. It is usually a dropped connection to the local server."
        onRetry={() => refetch()}
        retrying={isFetching}
      />
    );
  }

  const items = data.pages.flatMap((page) => page.items);
  if (items.length === 0) {
    return (
      <EmptyState
        icon={emptyIcon}
        title={emptyTitle ?? "Nothing here yet"}
        description={emptyDescription ?? "No clips match this view."}
        action={emptyAction}
      />
    );
  }

  const total = data.pages[0]?.total_matched ?? items.length;
  return (
    <div>
      <div className={styles.toolbar}>
        <p className={styles.count} aria-live="polite">
          Showing {items.length} of {total}
        </p>
        <div className={styles.toolbarActions}>
          {queueContext ? <PlayAll items={items} context={queueContext} /> : null}
          {/* Entering selection mode swaps the cards' hover affordances for checkboxes. */}
          {selection.active ? null : (
            <Button variant="subtle" icon={Icons.confirm} onClick={() => selection.setActive(true)}>
              Select
            </Button>
          )}
        </div>
      </div>
      <ClipGrid items={items} label={title} selection={selection} />
      <SelectionBar selection={selection} allIds={items.map((item) => item.id)} />

      {hasNextPage ? (
        <div className={styles.more}>
          <Button
            icon={Icons.chevronDown}
            loading={isFetchingNextPage}
            onClick={() => fetchNextPage()}
          >
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}
