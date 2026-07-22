import type { ClipSummary } from "../api/types";

/** Build a ClipSummary for tests, overriding only the fields a case cares about. */
export function makeClip(overrides: Partial<ClipSummary> = {}): ClipSummary {
  return {
    id: "IG_COOK1",
    platform: "instagram",
    author: "chef",
    caption: "One-pan pasta",
    likes: 12_340,
    views: 250_000,
    comments_count: 42,
    duration_seconds: 75,
    published_at: "2026-01-01T00:00:00+00:00",
    downloaded_at: "2026-01-02T00:00:00+00:00",
    available: true,
    metadata_state: "complete",
    hashtags: ["pasta"],
    topics: ["cooking"],
    source_url: "https://example.com/p/1",
    ...overrides,
  };
}
