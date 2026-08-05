import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Insights } from "../api/types";
import { InsightsPage, formatWatchTime } from "./InsightsPage";

function insights(over: Partial<Insights> = {}): Insights {
  return {
    totals: {
      clips: 100,
      watched_clips: 25,
      unwatched_clips: 75,
      completed_clips: 10,
      plays: 40,
      watch_time_seconds: 5400,
    },
    top_creators: [{ creator: "chefana", plays: 12, clips: 4 }],
    top_topics: [{ topic: "health-and-fitness", plays: 9, clips: 3 }],
    activity: [
      { day: "2026-08-01", clips: 3 },
      { day: "2026-08-02", clips: 7 },
    ],
    ...over,
  };
}

let payload: Insights;

beforeEach(() => {
  payload = insights();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
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
        <InsightsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("formatWatchTime keeps the largest unit that still reads precisely", () => {
  expect(formatWatchTime(45)).toBe("45s");
  expect(formatWatchTime(600)).toBe("10 min");
  expect(formatWatchTime(5400)).toBe("1 hr 30 min");
  expect(formatWatchTime(7200)).toBe("2 hr");
});

test("shows the headline figures with what they mean", async () => {
  renderPage();
  expect(await screen.findByText("1 hr 30 min")).toBeInTheDocument();
  // The definition travels with the number, so it cannot be misread as total playtime.
  expect(screen.getByText(/furthest point reached in each clip/i)).toBeInTheDocument();
  expect(screen.getByText("75")).toBeInTheDocument();
  expect(screen.getByText("collected, never opened")).toBeInTheDocument();
});

test("every leaderboard entry drills through to its clips", async () => {
  renderPage();
  expect(await screen.findByRole("link", { name: "chefana" })).toHaveAttribute(
    "href",
    "/explore?creator=chefana",
  );
  expect(screen.getByRole("link", { name: "Health And Fitness" })).toHaveAttribute(
    "href",
    "/topics/health-and-fitness",
  );
});

test("the activity chart keeps its numbers available as text", async () => {
  renderPage();
  const chart = await screen.findByLabelText("Clips played per day");
  expect(chart).toHaveTextContent("2026-08-02: 7 clips");
  expect(chart).toHaveTextContent("2026-08-01: 3 clips");
});

test("says plainly that nothing is sent anywhere", async () => {
  renderPage();
  expect(await screen.findByText(/Nothing is sent anywhere/i)).toBeInTheDocument();
});

test("an empty library reads as intentional, with the one useful next step", async () => {
  payload = insights({
    totals: {
      clips: 0,
      watched_clips: 0,
      unwatched_clips: 0,
      completed_clips: 0,
      plays: 0,
      watch_time_seconds: 0,
    },
    top_creators: [],
    top_topics: [],
    activity: [],
  });
  renderPage();

  expect(await screen.findByText("Nothing to summarize yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Add reels/ })).toHaveAttribute("href", "/downloads");
});

test("a library with plays but no topics explains the gap instead of showing an empty list", async () => {
  payload = insights({ top_topics: [] });
  renderPage();
  expect(await screen.findByText(/No topics assigned yet/)).toBeInTheDocument();
});
