import {
  type QueryKey,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  Account,
  Bootstrap,
  ClipDetail,
  ClipPage,
  ClipSummary,
  CollectionSummary,
  CommentPage,
  Diagnostics,
  DirListing,
  ForgetReport,
  HomeResponse,
  Insights,
  Job,
  LibrarySummary,
  MissingPage,
  PlaybackView,
  RescanReport,
  SearchResponse,
  TopicSummary,
  Transcript,
} from "./types";

export interface CollectionFilters {
  min_likes?: number;
  topics?: string[];
  platforms?: string[];
}

export interface PlaybackWrite {
  clipId: string;
  positionMs: number;
  durationMs?: number | null;
  completed?: boolean;
}

export function useBootstrap() {
  return useQuery({
    queryKey: ["bootstrap"],
    queryFn: () => apiGet<Bootstrap>("/api/v1/bootstrap"),
  });
}

/** Activate a registered library, then refresh everything that depends on the active library. */
export function useActivateLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (libraryId: string) =>
      apiPost<unknown>(`/api/v1/libraries/${encodeURIComponent(libraryId)}/activate`),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}

/**
 * Browse the server machine's directories to pick a library folder during onboarding. Sandboxed to
 * the user's home directory server-side: directory names only, never file contents. A null path
 * starts at home.
 */
export function useDirListing(path: string | null) {
  return useQuery({
    queryKey: ["fs-dirs", path],
    queryFn: () => {
      const query = path ? `?path=${encodeURIComponent(path)}` : "";
      return apiGet<DirListing>(`/api/v1/fs/dirs${query}`);
    },
  });
}

/** Register a library folder, then refresh the registry. Errors surface the sanitized message. */
export function useRegisterLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { display_name: string; path: string }) =>
      apiPost<LibrarySummary>("/api/v1/libraries", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bootstrap"] });
      queryClient.invalidateQueries({ queryKey: ["libraries"] });
    },
  });
}

/** Re-index a library from disk so files added out-of-band or by a download appear. */
export function useRescanLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (libraryId: string) =>
      apiPost<{ library: LibrarySummary; report: RescanReport }>(
        `/api/v1/libraries/${encodeURIComponent(libraryId)}/rescan`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}

/** Remove a library's registration (never its files), then refresh the registry. */
export function useUnregisterLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (libraryId: string) =>
      apiDelete<unknown>(`/api/v1/libraries/${encodeURIComponent(libraryId)}`),
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}

/** The full library registry (independent of the active-library-centric bootstrap payload). */
export function useLibraries() {
  return useQuery({
    queryKey: ["libraries"],
    queryFn: () => apiGet<{ libraries: LibrarySummary[] }>("/api/v1/libraries"),
  });
}

/**
 * Poll the job list. While any job is active, refetch on an interval as the SSE-free fallback.
 * When a download job newly reaches `succeeded`, the freshly downloaded clips are already in the
 * catalog, so invalidate the content caches — Home, library lists, search — to surface them without
 * a manual rescan (#135).
 */
export function useJobs() {
  const queryClient = useQueryClient();
  const settled = useRef<Set<string>>(new Set());
  const primed = useRef(false);
  const query = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiGet<{ jobs: Job[] }>("/api/v1/jobs"),
    refetchInterval: (q) => {
      const jobs = q.state.data?.jobs ?? [];
      const active = jobs.some((job) => job.state === "queued" || job.state === "running");
      return active ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!query.data) {
      return;
    }
    let landed = false;
    for (const job of query.data.jobs) {
      if (job.state === "succeeded" && !settled.current.has(job.id)) {
        settled.current.add(job.id);
        // The first poll primes the set with already-finished jobs; only downloads that complete
        // while the app is open should trigger a refresh.
        if (primed.current && job.result?.downloaded) {
          landed = true;
        }
      }
    }
    primed.current = true;
    if (landed) {
      // Clip lists live under many keys (home, topic, collection, queue, search…); a completed
      // download is rare, so refresh everything to guarantee the new clips surface.
      queryClient.invalidateQueries();
    }
  }, [query.data, queryClient]);

  return query;
}

export function useEnqueueJob() {
  const queryClient = useQueryClient();
  return useMutation({
    // An empty url means "your feed"; a leading @handle downloads a single account.
    mutationFn: (input: { url?: string; count?: number; quality?: string }) =>
      apiPost<Job>("/api/v1/jobs", {
        kind: "download",
        url: input.url ?? "",
        count: input.count ?? 1,
        quality: input.quality,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/** Per-platform sign-in status; polls while a connection is in progress. */
export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<{ accounts: Account[] }>("/api/v1/accounts"),
    refetchInterval: (query) =>
      (query.state.data?.accounts ?? []).some((a) => a.state === "connecting") ? 1500 : false,
  });
}

/** Start a one-time sign-in for a platform (opens a browser window on the user's machine). */
export function useConnectAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (platform: string) =>
      apiPost<Account>(`/api/v1/accounts/${encodeURIComponent(platform)}/connect`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => apiPost<Job>(`/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useDiagnostics() {
  return useQuery({
    queryKey: ["diagnostics"],
    queryFn: () => apiGet<Diagnostics>("/api/v1/diagnostics"),
  });
}

export function useHome() {
  return useQuery({
    queryKey: ["home"],
    queryFn: () => apiGet<HomeResponse>("/api/v1/home"),
  });
}

/**
 * Every saved collection. `enabled` lets a surface that only needs them on demand — the
 * add-to-collection dialog, opened from a card — avoid fetching until it opens.
 */
/** Library and viewing aggregates. Read-only: opening this records nothing. */
export function useInsights() {
  return useQuery({
    queryKey: ["insights"],
    queryFn: () => apiGet<Insights>("/api/v1/insights"),
  });
}

export function useCollections(enabled = true) {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => apiGet<{ collections: CollectionSummary[] }>("/api/v1/collections"),
    enabled,
  });
}

/**
 * One collection, including which clips are pinned into it. Keyed separately from the paginated
 * `["collection", id]` clip list the detail page loads — same resource, different shape.
 */
export function useCollection(id: string | undefined) {
  return useQuery({
    queryKey: ["collection-summary", id],
    queryFn: () => apiGet<CollectionSummary>(`/api/v1/collections/${encodeURIComponent(id ?? "")}`),
    enabled: Boolean(id),
  });
}

/**
 * Refresh everything a membership change can be seen through: the collection index, the rails on
 * Home, this collection's own summary, and the clip list the detail page pages through.
 */
function invalidateCollection(queryClient: ReturnType<typeof useQueryClient>, id?: string) {
  queryClient.invalidateQueries({ queryKey: ["collections"] });
  queryClient.invalidateQueries({ queryKey: ["home"] });
  if (id) {
    queryClient.invalidateQueries({ queryKey: ["collection-summary", id] });
    queryClient.invalidateQueries({ queryKey: ["collection", id] });
  }
}

export function useCreateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    // A null filter creates a collection with no query at all: its members are only `clips`.
    mutationFn: (input: { name: string; filters: CollectionFilters | null; clips?: string[] }) =>
      apiPost<CollectionSummary>("/api/v1/collections", input),
    onSuccess: (summary) => invalidateCollection(queryClient, summary.id),
  });
}

export function useUpdateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; filters: CollectionFilters | null }) =>
      apiPut<CollectionSummary>(`/api/v1/collections/${encodeURIComponent(input.id)}`, {
        filters: input.filters,
      }),
    onSuccess: (summary) => invalidateCollection(queryClient, summary.id),
  });
}

export function useDeleteCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiDelete<unknown>(`/api/v1/collections/${encodeURIComponent(id)}`),
    onSuccess: (_result, id) => invalidateCollection(queryClient, id),
  });
}

/** Pin clips into a collection, whatever its filter matches. Bulk-capable and idempotent. */
export function useAddClipsToCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; clipIds: string[] }) =>
      apiPost<CollectionSummary>(`/api/v1/collections/${encodeURIComponent(input.id)}/clips`, {
        clip_ids: input.clipIds,
      }),
    onSuccess: (summary) => invalidateCollection(queryClient, summary.id),
  });
}

/** Unpin one clip. A clip the collection's filter still matches stays in it. */
export function useRemoveClipFromCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; clipId: string }) =>
      apiDelete<CollectionSummary>(
        `/api/v1/collections/${encodeURIComponent(input.id)}/clips/${encodeURIComponent(input.clipId)}`,
      ),
    onSuccess: (_result, input) => invalidateCollection(queryClient, input.id),
  });
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: () => apiGet<{ topics: TopicSummary[] }>("/api/v1/topics"),
  });
}

export function useClipDetail(clipId: string | undefined) {
  return useQuery({
    queryKey: ["clip", clipId],
    queryFn: () => apiGet<ClipDetail>(`/api/v1/clips/${encodeURIComponent(clipId ?? "")}`),
    enabled: Boolean(clipId),
  });
}

/**
 * A clip's stored transcript. Fetched only when a panel asks for it — the detail payload
 * deliberately reports that a transcript exists without carrying its body.
 */
export function useTranscript(clipId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["transcript", clipId],
    queryFn: () =>
      apiGet<Transcript>(`/api/v1/clips/${encodeURIComponent(clipId ?? "")}/transcript`),
    enabled: Boolean(clipId) && enabled,
  });
}

/** One page of a clip's captured comments. */
export function useComments(clipId: string | undefined, enabled = true, limit = 50) {
  return useQuery({
    queryKey: ["comments", clipId, limit],
    queryFn: () =>
      apiGet<CommentPage>(
        `/api/v1/clips/${encodeURIComponent(clipId ?? "")}/comments?limit=${limit}`,
      ),
    enabled: Boolean(clipId) && enabled,
  });
}

/** Clips whose media file has gone missing — the only view that shows unavailable clips. */
export function useMissingClips(limit = 200) {
  return useQuery({
    queryKey: ["missing-media", limit],
    queryFn: () => apiGet<MissingPage>(`/api/v1/maintenance/missing?limit=${limit}`),
  });
}

/**
 * Drop catalog records for clips whose media is gone. Never deletes a file — the server re-checks
 * presence and reports anything it kept, so a stale list cannot remove a clip that came back.
 */
export function useForgetMissing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (clipIds: string[]) =>
      apiPost<ForgetReport>("/api/v1/maintenance/missing/forget", { clip_ids: clipIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["missing-media"] });
      queryClient.invalidateQueries({ queryKey: ["diagnostics"] });
    },
  });
}

/** Deterministic "more like this" recommendations for a clip. */
export function useRelated(clipId: string | undefined) {
  return useQuery({
    queryKey: ["related", clipId],
    queryFn: () =>
      apiGet<{ items: ClipSummary[] }>(`/api/v1/clips/${encodeURIComponent(clipId ?? "")}/related`),
    enabled: Boolean(clipId),
  });
}

export function useFavorite(clipId: string | undefined) {
  return useQuery({
    queryKey: ["favorite", clipId],
    queryFn: () =>
      apiGet<{ favorite: boolean }>(`/api/v1/clips/${encodeURIComponent(clipId ?? "")}/favorite`),
    enabled: Boolean(clipId),
  });
}

/** Toggle a clip's favorite state with an optimistic flip and rollback on failure. */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ clipId, favorite }: { clipId: string; favorite: boolean }) => {
      const path = `/api/v1/clips/${encodeURIComponent(clipId)}/favorite`;
      return favorite ? apiPut<unknown>(path) : apiDelete<unknown>(path);
    },
    onMutate: async ({ clipId, favorite }) => {
      const key = ["favorite", clipId];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ favorite: boolean }>(key);
      queryClient.setQueryData(key, { favorite });
      return { key, previous };
    },
    onError: (_err, _vars, context) => {
      if (context) {
        queryClient.setQueryData(context.key, context.previous);
      }
    },
    onSettled: (_data, _err, { clipId }) => {
      queryClient.invalidateQueries({ queryKey: ["favorite", clipId] });
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
    },
  });
}

/** Cursor-paginated search. Disabled until there is a non-empty query. */
export function useSearch(query: string, mode: string) {
  const trimmed = query.trim();
  return useInfiniteQuery({
    queryKey: ["search", trimmed, mode],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ q: trimmed, mode, limit: "24" });
      if (pageParam) {
        params.set("cursor", pageParam);
      }
      return apiGet<SearchResponse>(`/api/v1/search?${params.toString()}`);
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: trimmed.length > 0,
  });
}

export function usePlayback(clipId: string | undefined) {
  return useQuery({
    queryKey: ["playback", clipId],
    queryFn: () =>
      apiGet<{ playback: PlaybackView | null }>(
        `/api/v1/clips/${encodeURIComponent(clipId ?? "")}/playback`,
      ),
    enabled: Boolean(clipId),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** Persist playback progress, then refresh the home rails so Continue Watching stays current. */
export function useSavePlayback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (write: PlaybackWrite) =>
      apiPut<{ playback: PlaybackView }>(
        `/api/v1/clips/${encodeURIComponent(write.clipId)}/playback`,
        {
          position_ms: Math.round(write.positionMs),
          duration_ms: write.durationMs == null ? null : Math.round(write.durationMs),
          completed: write.completed,
        },
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["playback", variables.clipId] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
    },
  });
}

/**
 * Cursor-paginated clip list. `buildPath(cursor)` returns the request path for a page; a null cursor
 * requests the first page. Powers topic pages, "see all" rails, and library browsing.
 */
export function useClipList(
  key: QueryKey,
  buildPath: (cursor: string | null) => string,
  options: { enabled?: boolean } = {},
) {
  return useInfiniteQuery({
    queryKey: key,
    queryFn: ({ pageParam }) => apiGet<ClipPage>(buildPath(pageParam)),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: options.enabled ?? true,
  });
}
