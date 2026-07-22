import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { HomePage } from "./HomePage";

const ACTIVE_LIBRARY = {
  id: "lib1",
  display_name: "Reels",
  last_opened_at: null,
  health: "ready",
  clip_count: 3,
  is_active: true,
};

const BOOTSTRAP = {
  app_version: "0.2.0",
  active_library: ACTIVE_LIBRARY,
  libraries: [ACTIVE_LIBRARY],
  capabilities: {},
  worker: { state: "not_configured" },
};

const HOME = {
  rails: [
    {
      id: "recent",
      title: "Recently Added",
      kind: "recent",
      destination: "/library/recent",
      items: [makeClip({ id: "A", caption: "Alpha" }), makeClip({ id: "B", caption: "Beta" })],
      next_cursor: null,
    },
    {
      id: "topic:cooking",
      title: "Cooking",
      kind: "topic",
      destination: "/topics/cooking",
      items: [makeClip({ id: "C", caption: "Gamma" })],
      next_cursor: null,
    },
  ],
};

function jsonFor(url: string) {
  if (url.includes("/home")) {
    return HOME;
  }
  return BOOTSTRAP;
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

function renderHome() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders a hero and the server-ordered rails", async () => {
  renderHome();
  expect(await screen.findByRole("region", { name: "Recently Added" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Cooking" })).toBeInTheDocument();
  // The see-all link uses the server-provided destination.
  const seeAll = screen.getAllByRole("link", { name: "See all →" })[0];
  expect(seeAll).toHaveAttribute("href", "/library/recent");
});
