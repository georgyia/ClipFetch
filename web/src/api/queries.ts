import {
  type QueryKey,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  Bootstrap,
  ClipDetail,
  ClipPage,
  ClipSummary,
  CollectionSummary,
  Diagnostics,
  HomeResponse,
  Job,
  PlaybackView,
  SearchResponse,
  TopicSummary,
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

/** Poll the job list. While any job is active, refetch on an interval as the SSE-free fallback. */
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiGet<{ jobs: Job[] }>("/api/v1/jobs"),
    refetchInterval: (query) => {
      const jobs = query.state.data?.jobs ?? [];
      const active = jobs.some((job) => job.state === "queued" || job.state === "running");
      return active ? 2000 : false;
    },
  });
}

export function useEnqueueJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { url: string; count?: number }) =>
      apiPost<Job>("/api/v1/jobs", { kind: "download", url: input.url, count: input.count ?? 1 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
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

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => apiGet<{ collections: CollectionSummary[] }>("/api/v1/collections"),
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; filters: CollectionFilters }) =>
      apiPost<CollectionSummary>("/api/v1/collections", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
    },
  });
}

export function useUpdateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; filters: CollectionFilters }) =>
      apiPut<CollectionSummary>(`/api/v1/collections/${encodeURIComponent(input.id)}`, {
        filters: input.filters,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
    },
  });
}

export function useDeleteCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiDelete<unknown>(`/api/v1/collections/${encodeURIComponent(id)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
    },
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
