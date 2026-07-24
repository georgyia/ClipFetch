import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { DirListing, LibrarySummary } from "../api/types";
import { LibraryPage } from "./LibraryPage";

function makeLibrary(overrides: Partial<LibrarySummary>): LibrarySummary {
  return {
    id: "lib1",
    display_name: "My reels",
    last_opened_at: null,
    health: "ok",
    clip_count: 42,
    is_active: true,
    ...overrides,
  };
}

const HOME: DirListing = {
  cwd: "/home/me",
  parent: null,
  at_root: true,
  entries: [{ name: "clips", path: "/home/me/clips", is_library: true }],
};

let libraries: LibrarySummary[];

beforeEach(() => {
  libraries = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/fs/dirs")) {
        return new Response(JSON.stringify(HOME), { status: 200 });
      }
      if (url.endsWith("/libraries") && method === "POST") {
        const created = makeLibrary({ id: "new", display_name: "clips", is_active: false });
        libraries = [created];
        return new Response(JSON.stringify(created), { status: 201 });
      }
      if (url.includes("/activate")) {
        libraries = libraries.map((l) => ({ ...l, is_active: true }));
        return new Response(JSON.stringify(libraries[0]), { status: 200 });
      }
      if (url.includes("/rescan")) {
        return new Response(
          JSON.stringify({
            library: makeLibrary({}),
            report: { scanned: 5, inserted: 2, updated: 1, unchanged: 2, missing: 0 },
          }),
          { status: 200 },
        );
      }
      if (url.includes("/libraries/") && method === "DELETE") {
        libraries = [];
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify({ libraries }), { status: 200 });
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
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function lastCall(predicate: (url: string, init?: RequestInit) => boolean) {
  const matches = vi
    .mocked(globalThis.fetch)
    .mock.calls.filter(([u, init]) => predicate(String(u), init));
  return matches[matches.length - 1];
}

test("first run opens the add flow and lists folders from the sandbox root", async () => {
  renderPage();
  expect(await screen.findByRole("heading", { name: "Add a library" })).toBeInTheDocument();
  expect(await screen.findByText("clips")).toBeInTheDocument();
  // The folder that already holds a catalog is tagged.
  expect(screen.getByRole("button", { name: /clips Library/ })).toBeInTheDocument();
});

test("choosing a folder registers and activates a library", async () => {
  renderPage();
  await screen.findByRole("heading", { name: "Add a library" });
  fireEvent.click(await screen.findByRole("button", { name: "Use this folder" }));
  await waitFor(() => {
    const post = lastCall((u, init) => u.endsWith("/libraries") && init?.method === "POST");
    expect(post).toBeDefined();
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ path: "/home/me" });
  });
  await waitFor(() => expect(lastCall((u) => u.includes("/activate"))).toBeDefined());
});

test("shows registered libraries with clip count and health", async () => {
  libraries = [makeLibrary({})];
  renderPage();
  expect(await screen.findByText("My reels")).toBeInTheDocument();
  expect(screen.getByText(/42 clips · ok/)).toBeInTheDocument();
  expect(screen.getByText("Active")).toBeInTheDocument();
});

test("activates an inactive library", async () => {
  libraries = [makeLibrary({ id: "other", display_name: "Archive", is_active: false })];
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Activate" }));
  await waitFor(() => expect(lastCall((u) => u.includes("/other/activate"))).toBeDefined());
});

test("rescans a library and reports the counts", async () => {
  libraries = [makeLibrary({})];
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Rescan" }));
  expect(await screen.findByRole("status")).toHaveTextContent("2 new, 1 updated, 0 missing");
});

test("removing a library asks for confirmation and unregisters", async () => {
  libraries = [makeLibrary({})];
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
  await waitFor(() =>
    expect(
      lastCall((u, init) => u.includes("/libraries/lib1") && init?.method === "DELETE"),
    ).toBeDefined(),
  );
  confirm.mockRestore();
});
