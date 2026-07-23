import type { QueryKey } from "@tanstack/react-query";

// The vertical player's prev/next queue follows the set the viewer launched from — a topic,
// collection, Explore filter, or search — encoded as URL params on /watch/:id, so a deep link or a
// refresh reconstructs the same queue. With no context it falls back to global-recent.

const QUEUE_LIMIT = "50";
const EXPLORE_FIELDS = ["sort", "topic", "platform", "creator", "min_likes"] as const;

export interface QueueSource {
  key: QueryKey;
  buildPath: (cursor: string | null) => string;
}

export type QueueContext =
  | { from: "recent" }
  | { from: "topic"; key: string }
  | { from: "collection"; key: string }
  | { from: "search"; q: string; mode: string }
  | { from: "explore"; params: URLSearchParams };

function withCursor(base: string, cursor: string | null): string {
  if (!cursor) {
    return base;
  }
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}cursor=${encodeURIComponent(cursor)}`;
}

/** Resolve the queue's paginated endpoint from the /watch URL context. */
export function parseQueueSource(params: URLSearchParams): QueueSource {
  const from = params.get("from") ?? "recent";

  if (from === "topic") {
    const slug = params.get("key") ?? "";
    const base = `/api/v1/topics/${encodeURIComponent(slug)}/clips?limit=${QUEUE_LIMIT}&sort=date`;
    return { key: ["queue", "topic", slug], buildPath: (cursor) => withCursor(base, cursor) };
  }
  if (from === "collection") {
    const id = params.get("key") ?? "";
    const base = `/api/v1/collections/${encodeURIComponent(id)}/clips?limit=${QUEUE_LIMIT}&sort=date`;
    return { key: ["queue", "collection", id], buildPath: (cursor) => withCursor(base, cursor) };
  }
  if (from === "search") {
    const q = params.get("q") ?? "";
    const mode = params.get("mode") ?? "text";
    const query = new URLSearchParams({ q, mode, limit: QUEUE_LIMIT });
    const base = `/api/v1/search?${query.toString()}`;
    return { key: ["queue", "search", q, mode], buildPath: (cursor) => withCursor(base, cursor) };
  }
  if (from === "explore") {
    const query = new URLSearchParams({ limit: QUEUE_LIMIT, sort: params.get("sort") || "date" });
    for (const field of EXPLORE_FIELDS) {
      const value = params.get(field);
      if (value && field !== "sort") {
        query.set(field, value);
      }
    }
    const base = `/api/v1/clips?${query.toString()}`;
    return {
      key: ["queue", "explore", query.toString()],
      buildPath: (cursor) => withCursor(base, cursor),
    };
  }

  const base = `/api/v1/clips?limit=${QUEUE_LIMIT}&sort=date`;
  return { key: ["queue", "recent"], buildPath: (cursor) => withCursor(base, cursor) };
}

/** The /watch URL params that preserve a browsing surface's queue context. */
export function queueContextParams(context: QueueContext): URLSearchParams {
  const params = new URLSearchParams({ from: context.from });
  if (context.from === "topic" || context.from === "collection") {
    params.set("key", context.key);
  } else if (context.from === "search") {
    params.set("q", context.q);
    params.set("mode", context.mode);
  } else if (context.from === "explore") {
    for (const field of EXPLORE_FIELDS) {
      const value = context.params.get(field);
      if (value) {
        params.set(field, value);
      }
    }
  }
  return params;
}

/** A /watch link opening `clipId` while preserving the queue context (optionally shuffled). */
export function watchLink(
  clipId: string,
  context: QueueContext,
  options: { shuffle?: boolean } = {},
): string {
  const params = queueContextParams(context);
  if (options.shuffle) {
    params.set("shuffle", "1");
  }
  return `/watch/${encodeURIComponent(clipId)}?${params.toString()}`;
}
