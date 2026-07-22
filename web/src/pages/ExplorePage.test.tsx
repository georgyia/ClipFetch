import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      if (url.includes("/clips")) {
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

test("changing a filter updates the request query", async () => {
  renderExplore();
  await waitFor(() => expect(lastClipsUrl).toContain("/clips"));
  fireEvent.change(screen.getByLabelText("Platform"), { target: { value: "tiktok" } });
  await waitFor(() => expect(lastClipsUrl).toContain("platform=tiktok"));
});

test("hydrates filter controls from the URL", async () => {
  renderExplore("/explore?sort=likes&topic=cooking");
  await waitFor(() => expect(lastClipsUrl).toContain("sort=likes"));
  expect((screen.getByLabelText("Sort") as HTMLSelectElement).value).toBe("likes");
  // The topic option appears once the topics query resolves.
  await waitFor(() =>
    expect((screen.getByLabelText("Topic") as HTMLSelectElement).value).toBe("cooking"),
  );
});
