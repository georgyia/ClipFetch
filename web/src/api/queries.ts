import {
  type QueryKey,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "./client";
import type {
  Bootstrap,
  ClipDetail,
  ClipPage,
  HomeResponse,
  PlaybackView,
  TopicSummary,
} from "./types";

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

export function useHome() {
  return useQuery({
    queryKey: ["home"],
    queryFn: () => apiGet<HomeResponse>("/api/v1/home"),
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
 * Cursor-paginated clip list. `buildPath(cursor)` returns the request path for a page; a null cursor
 * requests the first page. Powers topic pages, "see all" rails, and library browsing.
 */
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
