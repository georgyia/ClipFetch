import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";

const BOOTSTRAP = {
  app_version: "0.2.0",
  active_library: null,
  libraries: [],
  capabilities: {},
  worker: { state: "not_configured" },
};

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(BOOTSTRAP), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders the primary navigation", () => {
  renderWithProviders(<App />);
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
});

test("shows library status from the bootstrap query", async () => {
  renderWithProviders(<App />);
  expect(await screen.findByText(/ClipFetch Watch v0\.2\.0/)).toBeInTheDocument();
});
