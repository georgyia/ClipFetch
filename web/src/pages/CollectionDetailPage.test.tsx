import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { CollectionDetailPage } from "./CollectionDetailPage";

const PINNED = "IG_TRAVEL1";
const MATCHED = "IG_COOK1";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let summary: { id: string; filters: Record<string, unknown> | null; pinned: string[] };

beforeEach(() => {
  summary = { id: "keepers", filters: { min_likes: 1000 }, pinned: [PINNED] };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if ((init?.method ?? "GET") === "DELETE") {
        summary = { ...summary, pinned: [] };
        return json({ ...summary, clip_count: 1, pinned_count: 0 });
      }
      if (url.includes("/clips")) {
        return json({
          schema_version: 1,
          items: [
            makeClip({ id: MATCHED, caption: "Matched by the filter" }),
            makeClip({ id: PINNED, caption: "Added by hand" }),
          ],
          next_cursor: null,
          total_matched: 2,
        });
      }
      return json({ ...summary, clip_count: 2, pinned_count: summary.pinned.length });
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
      <MemoryRouter initialEntries={["/collections/keepers"]}>
        <Routes>
          <Route path="/collections/:id" element={<CollectionDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("only hand-added clips offer a remove control", async () => {
  renderPage();
  await screen.findByRole("link", { name: "Added by hand" });

  // The filter-matched clip has no remove: this page cannot evict what the query put there.
  await waitFor(() =>
    expect(screen.getAllByRole("button", { name: "Remove from keepers" })).toHaveLength(1),
  );
});

test("removing a clip unpins it through the collection's clips endpoint", async () => {
  renderPage();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Remove from keepers" })).toBeTruthy(),
  );

  fireEvent.click(screen.getByRole("button", { name: "Remove from keepers" }));

  await waitFor(() => {
    const deletes = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([, init]) => init?.method === "DELETE");
    expect(deletes).toHaveLength(1);
    expect(deletes[0][0]).toBe(`/api/v1/collections/keepers/clips/${PINNED}`);
  });
});
