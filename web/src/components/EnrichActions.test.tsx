import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { ClipDetail, Job } from "../api/types";
import { makeClip } from "../test/fixtures";
import { EnrichActions } from "./EnrichActions";

function detail(over: Partial<ClipDetail> = {}): ClipDetail {
  return {
    ...makeClip(),
    schema_version: 1,
    shares: null,
    file_size_bytes: 1024,
    has_transcript: false,
    transcript_status: null,
    transcript_language: null,
    has_comments: false,
    comment_status: null,
    media: null,
    ...over,
  };
}

function job(over: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    kind: "enrich",
    state: "queued",
    source_permalink: null,
    phase: null,
    progress_current: null,
    progress_total: null,
    attempt: 0,
    max_attempts: 3,
    cancel_requested: false,
    error: null,
    result: null,
    created_at: "2026-08-05T00:00:00+00:00",
    started_at: null,
    finished_at: null,
    updated_at: "2026-08-05T00:00:00+00:00",
    ...over,
  };
}

let jobs: Job[];
let enqueueResponse: () => Response;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  jobs = [];
  enqueueResponse = () => json(job(), 201);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        const response = enqueueResponse();
        if (response.status === 201) {
          // Mirror the server: an accepted job is in the list from the next poll onwards, which
          // is also what keeps useJobs polling while it is active.
          jobs = [job()];
        }
        return response;
      }
      return json({ jobs });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderActions(clip = detail()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <EnrichActions clip={clip} />
    </QueryClientProvider>,
  );
}

test("offers only the enrichment a clip is missing", () => {
  renderActions(detail({ has_transcript: true }));
  expect(screen.queryByRole("button", { name: "Add transcript" })).toBeNull();
  expect(screen.getByRole("button", { name: "Fetch comments" })).toBeInTheDocument();
});

test("renders nothing for a clip that already has both", () => {
  const { container } = renderActions(detail({ has_transcript: true, has_comments: true }));
  expect(container).toBeEmptyDOMElement();
});

test("asking for a transcript enqueues an enrichment job for this clip", async () => {
  renderActions();
  fireEvent.click(screen.getByRole("button", { name: "Add transcript" }));

  await waitFor(() => {
    const posts = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      kind: "enrich",
      clip_id: "IG_COOK1",
      target: "transcript",
    });
  });
  expect(await screen.findByText(/Queued/)).toBeInTheDocument();
});

test("a refused prerequisite says what to install instead of queueing anything", async () => {
  enqueueResponse = () =>
    json(
      {
        error: {
          code: "transcription_unavailable",
          message: "Local transcription is not installed.",
        },
      },
      422,
    );
  renderActions();
  fireEvent.click(screen.getByRole("button", { name: "Add transcript" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent('pip install "clipfetch[transcribe]"');
});

test("a failed job explains the recovery rather than showing a raw code", async () => {
  renderActions();
  fireEvent.click(screen.getByRole("button", { name: "Fetch comments" }));
  await screen.findByText(/Queued/);

  jobs = [
    job({
      state: "failed",
      error: { code: "authentication_required", message: "sign in first" },
    }),
  ];

  // useJobs polls every 2s while a job is active, so allow for one poll.
  const alert = await screen.findByRole("alert", {}, { timeout: 5000 });
  expect(alert).toHaveTextContent(/Connect your Instagram account/);
});
