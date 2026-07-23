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

/** A /watch link opening `clipId` while preserving the queue context (optionally shuffled).
 *
 * A shuffle seed is carried in the URL so the shuffled order is stable across prev/next and a
 * refresh — every clip in the session shares the same seed.
 */
export function watchLink(
  clipId: string,
  context: QueueContext,
  options: { shuffle?: boolean; seed?: number } = {},
): string {
  const params = queueContextParams(context);
  if (options.shuffle) {
    params.set("shuffle", "1");
    params.set("seed", String(options.seed ?? Math.floor(Math.random() * 1_000_000_000)));
  }
  return `/watch/${encodeURIComponent(clipId)}?${params.toString()}`;
}

/** Deterministic Fisher–Yates shuffle (mulberry32) — same seed and input give the same order. */
export function seededShuffle<T>(items: readonly T[], seed: number): T[] {
  const out = items.slice();
  let state = (seed || 1) >>> 0;
  const random = () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
