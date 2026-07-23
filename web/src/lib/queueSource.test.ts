import { describe, expect, test } from "vitest";
import { parseQueueSource, queueContextParams, seededShuffle, watchLink } from "./queueSource";

function path(params: string, cursor: string | null = null): string {
  return parseQueueSource(new URLSearchParams(params)).buildPath(cursor);
}

describe("parseQueueSource", () => {
  test("defaults to global-recent with no context", () => {
    const source = parseQueueSource(new URLSearchParams());
    expect(source.key).toEqual(["queue", "recent"]);
    expect(source.buildPath(null)).toBe("/api/v1/clips?limit=50&sort=date");
  });

  test("appends the cursor for pagination", () => {
    expect(path("", "abc123")).toBe("/api/v1/clips?limit=50&sort=date&cursor=abc123");
  });

  test("topic context targets the topic listing", () => {
    const source = parseQueueSource(new URLSearchParams("from=topic&key=cooking"));
    expect(source.key).toEqual(["queue", "topic", "cooking"]);
    expect(source.buildPath(null)).toBe("/api/v1/topics/cooking/clips?limit=50&sort=date");
  });

  test("collection context targets the collection listing", () => {
    expect(path("from=collection&key=favs")).toBe(
      "/api/v1/collections/favs/clips?limit=50&sort=date",
    );
  });

  test("search context targets the search endpoint", () => {
    expect(path("from=search&q=dogs&mode=semantic")).toBe(
      "/api/v1/search?q=dogs&mode=semantic&limit=50",
    );
  });

  test("explore context carries its filters", () => {
    const built = path("from=explore&sort=likes&topic=cooking&min_likes=1000&platform=instagram");
    expect(built).toContain("/api/v1/clips?");
    expect(built).toContain("sort=likes");
    expect(built).toContain("topic=cooking");
    expect(built).toContain("min_likes=1000");
    expect(built).toContain("platform=instagram");
    expect(built).toContain("limit=50");
  });
});

describe("watchLink round-trips through parseQueueSource", () => {
  test("topic play-all preserves the queue", () => {
    const link = watchLink("IG_1", { from: "topic", key: "cooking" });
    const query = link.split("?")[1];
    expect(parseQueueSource(new URLSearchParams(query)).buildPath(null)).toBe(
      "/api/v1/topics/cooking/clips?limit=50&sort=date",
    );
  });

  test("shuffle adds the shuffle flag", () => {
    const link = watchLink("IG_1", { from: "recent" }, { shuffle: true });
    expect(new URLSearchParams(link.split("?")[1]).get("shuffle")).toBe("1");
  });

  test("explore context params keep only the active filters", () => {
    const params = new URLSearchParams("sort=likes&topic=cooking&irrelevant=x");
    const ctx = queueContextParams({ from: "explore", params });
    expect(ctx.get("from")).toBe("explore");
    expect(ctx.get("sort")).toBe("likes");
    expect(ctx.get("topic")).toBe("cooking");
    expect(ctx.get("irrelevant")).toBeNull();
  });
});

describe("seededShuffle", () => {
  const items = ["a", "b", "c", "d", "e", "f", "g", "h"];

  test("is a permutation (same members, no loss)", () => {
    const shuffled = seededShuffle(items, 42);
    expect([...shuffled].sort()).toEqual([...items].sort());
    expect(shuffled).not.toBe(items); // does not mutate the input
  });

  test("is deterministic for a given seed", () => {
    expect(seededShuffle(items, 123)).toEqual(seededShuffle(items, 123));
  });

  test("different seeds generally give different orders", () => {
    expect(seededShuffle(items, 1)).not.toEqual(seededShuffle(items, 2));
  });
});
