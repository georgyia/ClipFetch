import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { ClipGrid } from "../components/ClipGrid";
import { PageTransition } from "./PageTransition";

/** Point matchMedia at a fixed prefers-reduced-motion answer. */
function stubReducedMotion(reduced: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: reduced && query.includes("reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

const CLIP = {
  id: "IG_1",
  platform: "instagram",
  author: "chef",
  caption: "A clip",
  likes: 10,
  views: null,
  comments_count: null,
  duration_seconds: 12,
  published_at: null,
  downloaded_at: "2026-01-01T00:00:00Z",
  available: true,
  metadata_state: "complete",
  hashtags: [],
  topics: [],
  source_url: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("wraps pages in an animated element by default", () => {
  stubReducedMotion(false);
  const { container } = render(
    <MemoryRouter>
      <PageTransition>
        <p>Content</p>
      </PageTransition>
    </MemoryRouter>,
  );
  // The wrapper carries the animation class; children are nested inside it.
  expect(container.firstElementChild?.tagName).toBe("DIV");
  expect(screen.getByText("Content")).toBeInTheDocument();
});

test("renders children untouched under reduced motion — no wrapper, no animation", () => {
  stubReducedMotion(true);
  const { container } = render(
    <MemoryRouter>
      <PageTransition>
        <p>Content</p>
      </PageTransition>
    </MemoryRouter>,
  );
  // No animated wrapper at all: the paragraph is the top-level node.
  expect(container.firstElementChild?.tagName).toBe("P");
});

test("the grid reveals immediately under reduced motion instead of waiting to be observed", () => {
  stubReducedMotion(true);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ClipGrid items={[CLIP]} label="Clips" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // data-revealed drives the entrance animation; true means the cards are visible from the start.
  expect(screen.getByLabelText("Clips")).toHaveAttribute("data-revealed", "true");
});
