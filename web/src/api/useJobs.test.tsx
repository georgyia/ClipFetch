import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Job } from "./types";
import { useJobs } from "./queries";

function makeJob(overrides: Partial<Job>): Job {
  return {
    id: "j1",
    kind: "download",
    state: "queued",
    source_permalink: "https://x/p/1",
    phase: null,
    progress_current: null,
    progress_total: null,
    attempt: 0,
    max_attempts: 3,
    cancel_requested: false,
    error: null,
    result: null,
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

let jobs: Job[];

beforeEach(() => {
  jobs = [makeJob({ id: "run", state: "running" })];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ jobs }), { status: 200 })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

test("refreshes content caches when a download job newly succeeds", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result, rerender } = renderHook(() => useJobs(), { wrapper: wrapper(client) });

  await waitFor(() => expect(result.current.data?.jobs[0]?.state).toBe("running"));
  const primingCalls = invalidate.mock.calls.length;

  // The running job finishes with downloaded clips; the next poll should trigger a full refresh.
  jobs = [
    makeJob({ id: "run", state: "succeeded", result: { downloaded: 2, clip_ids: ["A", "B"] } }),
  ];
  await result.current.refetch();
  rerender();

  await waitFor(() => expect(invalidate.mock.calls.length).toBeGreaterThan(primingCalls));
  // A blanket invalidation (no queryKey filter) is what surfaces new clips everywhere.
  expect(invalidate.mock.calls.some((call) => call.length === 0 || call[0] === undefined)).toBe(
    true,
  );
});

test("does not refresh for jobs already finished on first load", async () => {
  jobs = [makeJob({ id: "old", state: "succeeded", result: { downloaded: 5, clip_ids: [] } })];
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHook(() => useJobs(), { wrapper: wrapper(client) });

  await waitFor(() => expect(result.current.data?.jobs[0]?.state).toBe("succeeded"));
  // Priming must not fire a blanket invalidation for history.
  expect(invalidate.mock.calls.some((call) => call.length === 0 || call[0] === undefined)).toBe(
    false,
  );
});
