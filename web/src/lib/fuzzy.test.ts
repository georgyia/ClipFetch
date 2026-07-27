import { expect, test } from "vitest";
import { fuzzyMatch, rank } from "./fuzzy";

test("matches a subsequence and reports where it landed", () => {
  const result = fuzzyMatch("dl", "Downloads");
  expect(result).not.toBeNull();
  expect(result?.indices).toEqual([0, 4]);
});

test("rejects a query that is not a subsequence", () => {
  expect(fuzzyMatch("zzz", "Downloads")).toBeNull();
  // Order matters: both letters are present, but "s" never appears after the final "d".
  expect(fuzzyMatch("sd", "Downloads")).toBeNull();
});

test("an empty query matches everything with no highlight", () => {
  expect(fuzzyMatch("", "Anything")).toEqual({ score: 0, indices: [] });
});

test("a prefix match outranks a mid-word one", () => {
  const prefix = fuzzyMatch("se", "Settings");
  const middle = fuzzyMatch("se", "Browse everything");
  expect(prefix?.score).toBeGreaterThan(middle?.score ?? 0);
});

test("word-boundary initials rank above scattered letters", () => {
  const initials = fuzzyMatch("cw", "Continue watching");
  const scattered = fuzzyMatch("cw", "Chronological weekly archive");
  expect(initials?.score).toBeGreaterThan(scattered?.score ?? 0);
});

test("rank filters out non-matches and orders best first", () => {
  const items = ["Home", "Explore", "Downloads", "Settings"];
  const result = rank("do", items, (item) => item);
  expect(result.map((entry) => entry.item)).toEqual(["Downloads"]);
});

test("rank preserves the caller's order for an empty query", () => {
  const items = ["Home", "Explore", "Search"];
  expect(rank("  ", items, (item) => item).map((entry) => entry.item)).toEqual(items);
});

test("equal scores keep a stable order rather than reshuffling", () => {
  const items = ["Topic a", "Topic b", "Topic c"];
  const first = rank("topic", items, (item) => item).map((entry) => entry.item);
  const second = rank("topic", items, (item) => item).map((entry) => entry.item);
  expect(first).toEqual(second);
});
