import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { Bootstrap } from "./types";

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
