import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { ClipDetail } from "../api/types";
import { makeClip } from "../test/fixtures";
import { CommentsPanel } from "./CommentsPanel";

function detail(over: Partial<ClipDetail> = {}): ClipDetail {
  return {
    ...makeClip(),
    schema_version: 1,
    shares: null,
    file_size_bytes: 1024,
    has_transcript: false,
    transcript_status: null,
    transcript_language: null,
    has_comments: true,
    comment_status: "complete",
    media: null,
    ...over,
  };
}

function renderPanel(clip = detail()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <CommentsPanel clip={clip} />
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
            items: [
              { id: "c1", text: "this is great" },
              { id: "c2", text: "<script>alert(1)</script>" },
            ],
            total: 2,
            status: "complete",
            retrieved_at: "2026-06-01T00:00:00+00:00",
            next_offset: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders nothing for a clip whose comments were never fetched", () => {
  const { container } = renderPanel(detail({ has_comments: false, comment_status: null }));
  expect(container).toBeEmptyDOMElement();
});

test("says plainly that the comments are a snapshot, with its capture time", async () => {
  renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Show" }));

  const note = await screen.findByText(/2 kept/);
  expect(note).toHaveTextContent("captured");
  expect(note).toHaveTextContent(/not a live view/);
});

test("comment text is rendered as text, never as markup", async () => {
  const { container } = renderPanel();
  fireEvent.click(screen.getByRole("button", { name: "Show" }));

  expect(await screen.findByText("<script>alert(1)</script>")).toBeInTheDocument();
  expect(container.querySelector("script")).toBeNull();
});

test("a capture status that kept nothing explains why", () => {
  renderPanel(detail({ has_comments: false, comment_status: "disabled" }));
  expect(screen.getByText(/comments turned off/i)).toBeInTheDocument();
});
