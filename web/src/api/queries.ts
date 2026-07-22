import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { Bootstrap } from "./types";

export function useBootstrap() {
  return useQuery({
    queryKey: ["bootstrap"],
    queryFn: () => apiGet<Bootstrap>("/api/v1/bootstrap"),
  });
}
