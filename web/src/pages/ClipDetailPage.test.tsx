import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipDetailPage } from "./ClipDetailPage";

const DETAIL = {
  ...makeClip({ id: "IG_COOK1", caption: "One-pan pasta", topics: ["cooking"] }),
  schema_version: 1,
  shares: 12,
  file_size_bytes: 4_400_000,
  has_transcript: true,
  transcript_status: "ready",
  transcript_language: "en",
  has_comments: false,
  comment_status: null,
};

const TOPIC_CLIPS = {
  schema_version: 1,
  items: [makeClip({ id: "IG_COOK1" }), makeClip({ id: "IG_COOK2", caption: "Second" })],
  next_cursor: null,
  total_matched: 2,
};

function jsonFor(url: string) {
  if (url.includes("/topics/")) {
    return TOPIC_CLIPS;
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

function renderDetail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/clip/IG_COOK1"]}>
        <Routes>
          <Route path="/clip/:id" element={<ClipDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("shows metadata, a watch link, and technical details", async () => {
  renderDetail();
  expect(await screen.findByRole("heading", { name: "One-pan pasta" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Watch/ })).toHaveAttribute("href", "/watch/IG_COOK1");
  expect(screen.getByText("4.2 MB")).toBeInTheDocument();
  expect(screen.getByText("ready")).toBeInTheDocument();
});

test("shows a related rail excluding the current clip", async () => {
  renderDetail();
  const rail = await screen.findByRole("region", { name: "More like this" });
  expect(rail).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Second" })).toBeInTheDocument();
});

test("disables watch when media is unavailable", async () => {
  const gone = { ...DETAIL, available: false };
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(String(input).includes("/topics/") ? TOPIC_CLIPS : gone), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  renderDetail();
  expect(await screen.findByRole("button", { name: "Media unavailable" })).toBeDisabled();
});
