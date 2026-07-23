import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import type { ClipSummary } from "../api/types";
import { PlayAll } from "./PlayAll";

function clip(id: string, available = true): ClipSummary {
  return {
    id,
    platform: "instagram",
    author: null,
    caption: null,
    likes: null,
    views: null,
    comments_count: null,
    duration_seconds: null,
    published_at: null,
    downloaded_at: "2026-01-01T00:00:00Z",
    available,
    metadata_state: "complete",
    hashtags: [],
    topics: [],
    source_url: null,
  };
}

function Probe() {
  const loc = useLocation();
  return <div data-testid="loc">{loc.pathname + loc.search}</div>;
}

function renderPlayAll(items: ClipSummary[]) {
  return render(
    <MemoryRouter>
      <PlayAll items={items} context={{ from: "topic", key: "cooking" }} />
      <Probe />
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("Play all opens the first available clip with the queue context", () => {
  renderPlayAll([clip("AAA"), clip("BBB")]);
  fireEvent.click(screen.getByRole("button", { name: /play all/i }));
  expect(screen.getByTestId("loc").textContent).toBe("/watch/AAA?from=topic&key=cooking");
});

test("Play all skips unavailable clips when picking the start", () => {
  renderPlayAll([clip("GONE", false), clip("BBB")]);
  fireEvent.click(screen.getByRole("button", { name: /play all/i }));
  expect(screen.getByTestId("loc").textContent).toBe("/watch/BBB?from=topic&key=cooking");
});

test("Shuffle carries the context and a shuffle seed", () => {
  vi.spyOn(Math, "random").mockReturnValue(0); // start clip = first, seed = 0-derived
  renderPlayAll([clip("AAA"), clip("BBB")]);
  fireEvent.click(screen.getByRole("button", { name: /shuffle/i }));
  const value = screen.getByTestId("loc").textContent ?? "";
  expect(value).toContain("/watch/AAA?");
  expect(value).toContain("from=topic");
  expect(value).toContain("key=cooking");
  expect(value).toContain("shuffle=1");
  expect(value).toContain("seed=");
});

test("renders nothing when no clip is available", () => {
  const { container } = renderPlayAll([clip("GONE", false)]);
  expect(container.querySelectorAll("button")).toHaveLength(0);
});
