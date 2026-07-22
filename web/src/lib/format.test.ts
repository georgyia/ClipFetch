import { expect, test } from "vitest";
import { compactCount, formatDuration } from "./format";

test("compactCount abbreviates large numbers", () => {
  expect(compactCount(0)).toBe("0");
  expect(compactCount(999)).toBe("999");
  expect(compactCount(1234)).toBe("1.2K");
  expect(compactCount(2_500_000)).toBe("2.5M");
  expect(compactCount(150_000)).toBe("150K");
  expect(compactCount(3_000_000_000)).toBe("3B");
});

test("compactCount handles missing values", () => {
  expect(compactCount(null)).toBe("");
  expect(compactCount(undefined)).toBe("");
  expect(compactCount(-5)).toBe("");
});

test("formatDuration renders minutes and hours", () => {
  expect(formatDuration(0)).toBe("0:00");
  expect(formatDuration(9)).toBe("0:09");
  expect(formatDuration(75)).toBe("1:15");
  expect(formatDuration(3661)).toBe("1:01:01");
  expect(formatDuration(null)).toBe("");
});
