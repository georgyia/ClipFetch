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
  media: {
    tier: { slug: "full_hd", label: "Full HD", reason: "1080x1920 source" },
    status: "ok",
    width: 1080,
    height: 1920,
    video_codec: "h264",
  },
};

const RELATED = {
  items: [makeClip({ id: "IG_COOK2", caption: "Second" })],
};

function jsonFor(url: string) {
  if (url.includes("/related")) {
    return RELATED;
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

test("shows metadata, a play link, and technical details", async () => {
  renderDetail();
  expect(await screen.findByRole("heading", { name: "One-pan pasta" })).toBeInTheDocument();
  expect(screen.getByText("4.2 MB")).toBeInTheDocument();
  expect(screen.getByText("ready")).toBeInTheDocument();
  // Probed technical quality tier and resolution.
  expect(screen.getByText("Full HD")).toBeInTheDocument();
  expect(screen.getByText(/1080×1920/)).toBeInTheDocument();
});

test("Play carries queue context so next continues along the clip's topic", async () => {
  renderDetail();
  const play = await screen.findByRole("link", { name: /Play/ });
  const href = play.getAttribute("href") ?? "";
  expect(href).toContain("/watch/IG_COOK1");
  // The clip's first topic seeds the queue, rather than falling back to global-recent.
  expect(href).toContain("from=topic");
  expect(href).toContain("key=cooking");
});

test("falls back to the recent queue when a clip has no topics", async () => {
  const untagged = { ...DETAIL, topics: [] };
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(String(input).includes("/related") ? RELATED : untagged), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  renderDetail();
  const play = await screen.findByRole("link", { name: /Play/ });
  expect(play.getAttribute("href")).toContain("from=recent");
});

test("collapses a long caption behind a Show more toggle", async () => {
  const long = { ...DETAIL, caption: "x".repeat(500) };
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(String(input).includes("/related") ? RELATED : long), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  renderDetail();
  const toggle = await screen.findByRole("button", { name: "Show more" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");

  toggle.click();
  expect(await screen.findByRole("button", { name: "Show less" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
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
        new Response(JSON.stringify(String(input).includes("/related") ? RELATED : gone), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  renderDetail();
  expect(await screen.findByRole("button", { name: "Media unavailable" })).toBeDisabled();
});
