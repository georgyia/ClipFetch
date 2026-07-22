import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { PlayerPage } from "./PlayerPage";

const DETAIL = {
  ...makeClip({ id: "IG_COOK1", caption: "One-pan pasta" }),
  schema_version: 1,
  shares: null,
  file_size_bytes: 1000,
  has_transcript: false,
  transcript_status: null,
  transcript_language: null,
  has_comments: false,
  comment_status: null,
};

const QUEUE = {
  schema_version: 1,
  items: [makeClip({ id: "IG_COOK1" }), makeClip({ id: "IG_COOK2" })],
  next_cursor: null,
  total_matched: 2,
};

function jsonFor(url: string) {
  // The list endpoint has no trailing clip id segment.
  if (/\/clips\?/.test(url) || url.endsWith("/clips")) {
    return QUEUE;
  }
  return DETAIL;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(jsonFor(String(input))), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPlayer(start = "/watch/IG_COOK1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[start]}>
        <Routes>
          <Route path="/watch/:id" element={<PlayerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("streams the clip media by id and exposes transport controls", () => {
  const { container } = renderPlayer();
  const video = container.querySelector("video");
  expect(video).toHaveAttribute("src", "/api/v1/clips/IG_COOK1/media");
  expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: "Seek" })).toBeInTheDocument();
});

test("space toggles play/pause", () => {
  renderPlayer();
  expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  fireEvent.keyDown(window, { key: " " });
  expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
});

test("queue navigation enables next and disables previous at the head", async () => {
  renderPlayer();
  // Next becomes enabled once the recent-clips queue resolves.
  await waitFor(() => expect(screen.getByRole("button", { name: "Next clip" })).toBeEnabled());
  expect(screen.getByRole("button", { name: "Previous clip" })).toBeDisabled();
});
