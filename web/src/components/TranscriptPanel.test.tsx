import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { ClipDetail } from "../api/types";
import { makeClip } from "../test/fixtures";
import { TranscriptPanel, splitOnQuery } from "./TranscriptPanel";

const TEXT = "boil the pasta in salted water, then drain the pasta";

function detail(over: Partial<ClipDetail> = {}): ClipDetail {
  return {
    ...makeClip(),
    schema_version: 1,
    shares: null,
    file_size_bytes: 1024,
    has_transcript: true,
    transcript_status: "complete",
    transcript_language: "en",
    has_comments: false,
    comment_status: null,
    media: null,
    ...over,
  };
}

function renderPanel(clip = detail()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TranscriptPanel clip={clip} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            clip_id: "IG_COOK1",
            status: "complete",
            text: TEXT,
            language: "en",
            model_id: "fake/base",
            model_revision: "v1",
            updated_at: "2026-06-01T00:00:00+00:00",
            truncated: false,
            character_count: TEXT.length,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("splitOnQuery marks every occurrence and leaves the text intact", () => {
  const parts = splitOnQuery("the pasta and the sauce", "the");
  expect(parts.map((part) => part.text).join("")).toBe("the pasta and the sauce");
  expect(parts.filter((part) => part.match)).toHaveLength(2);
  // An empty query marks nothing rather than everything.
  expect(splitOnQuery("abc", "  ")).toEqual([{ text: "abc", match: false }]);
});

test("renders nothing for a clip that was never transcribed", () => {
  const { container } = renderPanel(detail({ has_transcript: false, transcript_status: null }));
  expect(container).toBeEmptyDOMElement();
});

test("fetches the body only once the panel is opened", async () => {
  renderPanel();
  expect(globalThis.fetch).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
  expect(await screen.findByText(/boil the pasta/)).toBeInTheDocument();
});

test("shows the provenance a transcript needs to be checkable", async () => {
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  expect(await screen.findByText(/fake\/base/)).toBeInTheDocument();
  expect(screen.getByText(/en ·/)).toBeInTheDocument();
});

test("find-within highlights matches and counts them", async () => {
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  await screen.findByText(/boil the pasta/);

  fireEvent.change(screen.getByLabelText("Find in transcript"), {
    target: { value: "pasta" },
  });

  expect(await screen.findByText("2 matches")).toBeInTheDocument();
  const marks = document.querySelectorAll("mark");
  expect(marks).toHaveLength(2);
  expect(marks[0].textContent).toBe("pasta");
});

test("a status with no text explains itself instead of showing an empty box", async () => {
  vi.mocked(globalThis.fetch).mockImplementation(
    async () =>
      new Response(
        JSON.stringify({
          clip_id: "IG_COOK1",
          status: "silent",
          text: null,
          language: null,
          model_id: "fake/base",
          model_revision: "v1",
          updated_at: null,
          truncated: false,
          character_count: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );
  renderPanel(detail({ has_transcript: false, transcript_status: "silent" }));

  expect(screen.getByText(/no speech was found/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  expect(await screen.findByText(/no transcript text/i)).toBeInTheDocument();
});
