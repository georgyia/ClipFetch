import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { CollectionSummary } from "../api/types";
import { AddToCollection } from "./AddToCollection";

function collection(id: string, over: Partial<CollectionSummary> = {}): CollectionSummary {
  return {
    id,
    filters: { min_likes: 1000 },
    clip_count: 3,
    pinned: [],
    pinned_count: 0,
    ...over,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let collections: CollectionSummary[] = [];

function renderDialog(clipIds: string[], onAdded?: () => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AddToCollection open onClose={() => {}} clipIds={clipIds} onAdded={onAdded} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  collections = [collection("keepers"), collection("big-hits", { pinned: ["A"], pinned_count: 1 })];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: RequestInfo | URL, init?: RequestInit) => {
      if (!init || init.method === undefined || init.method === "GET") {
        return json({ collections });
      }
      return json(collection("keepers"));
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("adds the clips to the chosen collection", async () => {
  const onAdded = vi.fn();
  renderDialog(["A", "B"], onAdded);

  await screen.findByText("keepers");
  expect(screen.getByRole("heading", { name: "Add 2 clips to a collection" })).toBeInTheDocument();

  fireEvent.click(screen.getAllByRole("button", { name: "Add" })[0]);

  await waitFor(() => {
    const posts = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe("/api/v1/collections/keepers/clips");
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ clip_ids: ["A", "B"] });
  });
  await waitFor(() => expect(onAdded).toHaveBeenCalled());
});

test("a collection that already holds every selected clip offers no repeat add", async () => {
  renderDialog(["A"]);
  await screen.findByText("big-hits");

  // "keepers" pins nothing; "big-hits" already pins A.
  expect(screen.getByRole("button", { name: "Add" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Added" })).toBeDisabled();
});

test("a new collection is created with no filter, so it holds only what was added", async () => {
  renderDialog(["A"]);
  await screen.findByText("keepers");

  fireEvent.change(screen.getByLabelText("New collection"), { target: { value: "watch-later" } });
  fireEvent.click(screen.getByRole("button", { name: "Create" }));

  await waitFor(() => {
    const posts = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(
        ([path, init]) => init?.method === "POST" && path === "/api/v1/collections",
      );
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
      name: "watch-later",
      filters: null,
      clips: ["A"],
    });
  });
});

test("a rejected add surfaces the server's message instead of closing", async () => {
  vi.mocked(globalThis.fetch).mockImplementation(async (_path, init?: RequestInit) => {
    if (!init || init.method === undefined || init.method === "GET") {
      return json({ collections });
    }
    return json({ error: { code: "clip_not_found", message: "clip id not found: A" } }, 404);
  });
  renderDialog(["A"]);
  await screen.findByText("keepers");

  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("clip id not found: A");
});
