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

const INSTAGRAM = {
  platform: "instagram",
  label: "Instagram",
  support: "full",
  state: "unknown",
  connected: false,
};

let jobs: Job[];

beforeEach(() => {
  jobs = [
    makeJob({ id: "active", state: "running", progress_current: 2, progress_total: 5 }),
    makeJob({
      id: "done",
      state: "succeeded",
      source_permalink: "https://x/p/2",
      result: { downloaded: 3, clip_ids: ["IG_A"] },
    }),
    makeJob({
      id: "authfail",
      state: "failed",
      error: { code: "authentication_required", message: "Not signed in to Instagram." },
    }),
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/accounts") && method === "GET") {
        return new Response(JSON.stringify({ accounts: [INSTAGRAM] }), { status: 200 });
      }
      if (url.includes("/accounts/") && url.endsWith("/connect")) {
        return new Response(JSON.stringify({ ...INSTAGRAM, state: "connecting" }), { status: 200 });
      }
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

function lastPost(path: string) {
  const calls = vi.mocked(globalThis.fetch).mock.calls;
  return calls.find(([u, init]) => String(u).endsWith(path) && init?.method === "POST");
}

test("groups active and finished jobs and shows progress", async () => {
  renderPage();
  expect(await screen.findByText("Active (1)")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/clip/IG_A");
});

test("downloads from the feed with the chosen count and quality", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.change(screen.getByLabelText("Count"), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "Download" }));
  await waitFor(() => {
    const post = lastPost("/jobs");
    expect(post).toBeDefined();
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      kind: "download",
      url: "",
      count: 12,
      quality: "high",
    });
  });
});

test("account mode downloads a single @handle", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.change(screen.getByLabelText("Source"), { target: { value: "account" } });
  fireEvent.change(screen.getByLabelText("Account"), { target: { value: "nasa" } });
  fireEvent.click(screen.getByRole("button", { name: "Download" }));
  await waitFor(() => {
    expect(JSON.parse(String(lastPost("/jobs")?.[1]?.body))).toMatchObject({ url: "@nasa" });
  });
});

test("Connect Instagram starts a sign-in", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.click(screen.getByRole("button", { name: "Connect Instagram" }));
  await waitFor(() => expect(lastPost("/accounts/instagram/connect")).toBeDefined());
});

test("an auth-required failure offers a Connect action", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  const connect = await screen.findByRole("button", { name: "Connect account" });
  fireEvent.click(connect);
  await waitFor(() => expect(lastPost("/accounts/instagram/connect")).toBeDefined());
});

test("cancels an active job", async () => {
  renderPage();
  await screen.findByText("Active (1)");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() =>
    expect(
      vi.mocked(globalThis.fetch).mock.calls.some(([u]) => String(u).includes("/cancel")),
    ).toBe(true),
  );
});
