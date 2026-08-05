import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { ExplorePage } from "./ExplorePage";

const TOPICS = { topics: [{ slug: "cooking", description: null, clip_count: 3 }] };

function pageFor(url: string) {
  if (url.includes("/topics")) {
    return TOPICS;
  }
  return {
    schema_version: 1,
    items: [makeClip({ id: "A", caption: "Alpha" })],
    next_cursor: null,
    total_matched: 1,
  };
}

let lastClipsUrl = "";

beforeEach(() => {
  lastClipsUrl = "";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      // Only the list endpoint. Cards now fetch /clips/<id>/favorite, which also contains
      // "/clips" and would otherwise clobber the URL under assertion.
      if (/\/clips\?/.test(url) || url.endsWith("/clips")) {
        lastClipsUrl = url;
      }
      return new Response(JSON.stringify(pageFor(url)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * Facet chips and active-filter chips deliberately share labels ("TikTok" appears in both rows),
 * so queries are scoped to one region or the other rather than searching the whole page.
 */
function facets() {
  return within(screen.getByLabelText("Filters"));
}

function renderExplore(initial = "/explore") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <ExplorePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("selecting a facet chip updates the request query", async () => {
  renderExplore();
  await waitFor(() => expect(lastClipsUrl).toContain("/clips"));

  fireEvent.click(facets().getByRole("button", { name: /TikTok/ }));
  await waitFor(() => expect(lastClipsUrl).toContain("platform=tiktok"));
});

test("a chip toggles off when its own value is re-selected", async () => {
  renderExplore("/explore?platform=tiktok");
  await waitFor(() => expect(lastClipsUrl).toContain("platform=tiktok"));

  const chip = facets().getByRole("button", { name: /TikTok/ });
  expect(chip).toHaveAttribute("aria-pressed", "true");

  fireEvent.click(chip);
  await waitFor(() => expect(lastClipsUrl).not.toContain("platform=tiktok"));
});

test("hydrates facet state from the URL", async () => {
  renderExplore("/explore?sort=likes&topic=cooking");
  await waitFor(() => expect(lastClipsUrl).toContain("sort=likes"));

  expect(facets().getByRole("button", { name: /Most liked/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(facets().getByRole("button", { name: /Newest/ })).toHaveAttribute("aria-pressed", "false");
  // The topic chip appears once the topics query resolves.
  await waitFor(() =>
    expect(facets().getByRole("button", { name: /Cooking/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );
});

test("active filters are listed as chips that clear individually", async () => {
  renderExplore("/explore?platform=tiktok&min_likes=10000");
  await waitFor(() => expect(lastClipsUrl).toContain("platform=tiktok"));

  const activeRow = screen.getByLabelText("Active filters");
  expect(within(activeRow).getByText("TikTok")).toBeInTheDocument();
  expect(within(activeRow).getByText("10K+ likes")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Remove TikTok filter" }));
  await waitFor(() => expect(lastClipsUrl).not.toContain("platform=tiktok"));
  // The other filter survives — removing one chip must not clear the rest.
  expect(lastClipsUrl).toContain("min_likes=10000");
});

test("Clear all drops every filter but keeps the sort preference", async () => {
  renderExplore("/explore?sort=likes&platform=tiktok&min_likes=10000");
  await waitFor(() => expect(lastClipsUrl).toContain("platform=tiktok"));

  fireEvent.click(screen.getByRole("button", { name: "Clear all" }));

  await waitFor(() => expect(lastClipsUrl).not.toContain("platform=tiktok"));
  expect(lastClipsUrl).not.toContain("min_likes");
  // Sort is a view preference, not a filter.
  expect(lastClipsUrl).toContain("sort=likes");
});

test("exports exactly the filters the view is showing", async () => {
  renderExplore("/explore?platform=tiktok&sort=likes");
  await screen.findByRole("link", { name: "Alpha" });

  const playlist = screen.getByRole("link", { name: /Playlist/ });
  const href = playlist.getAttribute("href") ?? "";
  expect(href).toContain("/api/v1/clips/export?");
  expect(href).toContain("platform=tiktok");
  expect(href).toContain("sort=likes");
  expect(href).toContain("format=m3u");
});

test("offers Play all and Shuffle so a filtered set becomes a queue", async () => {
  renderExplore();
  expect(
    await screen.findByRole("button", { name: "Play all clips in this view" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Shuffle-play clips in this view" }),
  ).toBeInTheDocument();
});
