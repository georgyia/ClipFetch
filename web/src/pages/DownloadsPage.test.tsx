import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Job } from "../api/types";
import { DownloadsPage } from "./DownloadsPage";

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
  jobs = [
    makeJob({
      id: "active",
      state: "running",
      progress_current: 2,
      progress_total: 5,
      phase: "downloading",
    }),
    makeJob({
      id: "done",
      state: "succeeded",
      source_permalink: "https://x/p/2",
      result: { downloaded: 3, clip_ids: ["IG_A"] },
    }),
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/jobs") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        const created = makeJob({ id: "new", source_permalink: body.url });
        jobs = [created, ...jobs];
        return new Response(JSON.stringify(created), { status: 201 });
      }
      if (url.includes("/cancel")) {
        jobs = jobs.map((job) => (job.id === "active" ? { ...job, state: "cancelled" } : job));
        return new Response(JSON.stringify(jobs[0]), { status: 200 });
      }
      return new Response(JSON.stringify({ jobs }), { status: 200 });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DownloadsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("groups active and finished jobs and shows progress", async () => {
  renderPage();
  expect(await screen.findByText("Active (1)")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  // The succeeded job links to its first clip.
  expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/clip/IG_A");
});

test("submitting a URL enqueues a download", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.change(screen.getByLabelText("Source URL"), {
    target: { value: "https://x/p/9" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Download" }));
  const fetchMock = vi.mocked(globalThis.fetch);
  await waitFor(() => {
    const post = fetchMock.mock.calls.find(
      ([u, init]) => String(u).endsWith("/jobs") && init?.method === "POST",
    );
    expect(post).toBeDefined();
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ url: "https://x/p/9" });
  });
});

test("cancels an active job", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  const fetchMock = vi.mocked(globalThis.fetch);
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/cancel"))).toBe(true),
  );
});
