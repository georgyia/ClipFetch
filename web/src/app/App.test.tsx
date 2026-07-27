import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
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

function renderWithProviders(ui: ReactElement, route = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
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

test("renders the primary navigation and brand", () => {
  renderWithProviders(<App />);
  const rail = screen.getByRole("navigation", { name: "Primary" });
  expect(within(rail).getByRole("link", { name: /Home/ })).toBeInTheDocument();
});

test("prompts to activate a library when none is active", async () => {
  renderWithProviders(<App />);
  expect(await screen.findByText("No active library")).toBeInTheDocument();
});

test("the header is transparent at the top and condenses once the page scrolls", () => {
  const { container } = renderWithProviders(<App />);
  const header = container.querySelector("header");
  expect(header).toHaveAttribute("data-condensed", "false");

  // jsdom never scrolls on its own, so drive scrollY directly and fire the event the hook listens
  // for — the assertion is about the hook's threshold logic, not about jsdom layout.
  Object.defineProperty(window, "scrollY", { value: 120, writable: true, configurable: true });
  fireEvent.scroll(window);

  expect(header).toHaveAttribute("data-condensed", "true");
});
