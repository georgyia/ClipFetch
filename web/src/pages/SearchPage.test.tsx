import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { SearchPage } from "./SearchPage";

function resultFor(url: string) {
  const semantic = url.includes("mode=meaning");
  return {
    query: "pasta",
    requested_mode: semantic ? "meaning" : "all",
    items: [makeClip({ id: "A", caption: "One-pan pasta" })],
    next_cursor: null,
    total_matched: 1,
    mode_used: "text",
    semantic_available: false,
  };
}

beforeEach(() => {
  window.localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(resultFor(String(input))), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSearch(initial = "/search") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <SearchPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("debounces input and shows results", async () => {
  renderSearch();
  fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "pasta" } });
  expect(await screen.findByRole("link", { name: "One-pan pasta" })).toBeInTheDocument();
  expect(screen.getByText(/1 results for "pasta"/)).toBeInTheDocument();
});

test("meaning mode shows a fallback notice when semantic is unavailable", async () => {
  renderSearch("/search?q=pasta&mode=meaning");
  expect(await screen.findByText(/Meaning search isn't available yet/)).toBeInTheDocument();
});

test("prompts before any query is entered", () => {
  renderSearch();
  expect(screen.getByText("Search your library")).toBeInTheDocument();
});
