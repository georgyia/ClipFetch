import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "vitest";

/*
 * Contrast is a release gate for this project, so it is asserted rather than eyeballed.
 *
 * The token values are parsed straight out of tokens.css — the file the app actually ships — so a
 * palette change that breaks AA fails here instead of shipping. Ratios follow WCAG 2.x relative
 * luminance; thresholds are 4.5:1 for body text, 3:1 for large text and UI boundaries.
 */

const CSS = readFileSync(resolve("src/styles/tokens.css"), "utf8");

/** Read a `--token: #hex;` declaration from a given selector block. */
function token(name: string, selector: string): string {
  const blockStart = CSS.indexOf(selector);
  if (blockStart === -1) {
    throw new Error(`selector ${selector} not found in tokens.css`);
  }
  const block = CSS.slice(blockStart, CSS.indexOf("\n}", blockStart));
  const match = block.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`));
  if (!match) {
    throw new Error(`token ${name} not found in ${selector}`);
  }
  return match[1];
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((char) => char + char)
          .join("")
      : clean;
  const r = Number.parseInt(full.slice(0, 2), 16);
  const g = Number.parseInt(full.slice(2, 4), 16);
  const b = Number.parseInt(full.slice(4, 6), 16);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [light, dark] = la > lb ? [la, lb] : [lb, la];
  return (light + 0.05) / (dark + 0.05);
}

const DARK = ":root {";
const LIGHT = ':root[data-theme="light"]';

test("contrast helper matches the known black-on-white extreme", () => {
  expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 1);
});

test("dark theme body text clears AA on every surface", () => {
  const text = token("--color-text", DARK);
  for (const surface of ["--color-bg", "--color-surface", "--color-surface-raised"]) {
    expect(contrast(text, token(surface, DARK))).toBeGreaterThanOrEqual(4.5);
  }
});

test("dark theme secondary and muted text clear AA on the page background", () => {
  const bg = token("--color-bg", DARK);
  expect(contrast(token("--color-text-secondary", DARK), bg)).toBeGreaterThanOrEqual(4.5);
  expect(contrast(token("--color-text-muted", DARK), bg)).toBeGreaterThanOrEqual(4.5);
});

test("light theme body text clears AA on every surface", () => {
  const text = token("--color-text", LIGHT);
  for (const surface of ["--color-bg", "--color-surface", "--color-surface-hover"]) {
    expect(contrast(text, token(surface, LIGHT))).toBeGreaterThanOrEqual(4.5);
  }
});

test("light theme secondary and muted text clear AA on the page background", () => {
  const bg = token("--color-bg", LIGHT);
  expect(contrast(token("--color-text-secondary", LIGHT), bg)).toBeGreaterThanOrEqual(4.5);
  expect(contrast(token("--color-text-muted", LIGHT), bg)).toBeGreaterThanOrEqual(4.5);
});

/*
 * The accent is deepened in the light theme precisely because the dark theme's coral would only
 * reach ~3:1 on white. This is the assertion that keeps that decision honest.
 */
test("the accent clears AA as text in both themes", () => {
  expect(contrast(token("--color-accent", DARK), token("--color-bg", DARK))).toBeGreaterThanOrEqual(
    4.5,
  );
  expect(
    contrast(token("--color-accent", LIGHT), token("--color-bg", LIGHT)),
  ).toBeGreaterThanOrEqual(4.5);
});

test("the focus ring is visible against the page in both themes", () => {
  // 3:1 is the WCAG 2.2 threshold for non-text UI components such as focus indicators.
  expect(contrast(token("--color-focus", DARK), token("--color-bg", DARK))).toBeGreaterThanOrEqual(
    3,
  );
  expect(
    contrast(token("--color-focus", LIGHT), token("--color-bg", LIGHT)),
  ).toBeGreaterThanOrEqual(3);
});

test("status colours clear AA as text on the page background in both themes", () => {
  for (const [selector, label] of [
    [DARK, "dark"],
    [LIGHT, "light"],
  ] as const) {
    const bg = token("--color-bg", selector);
    for (const status of ["--color-success", "--color-warning", "--color-danger", "--color-info"]) {
      const ratio = contrast(token(status, selector), bg);
      expect(ratio, `${status} in ${label}`).toBeGreaterThanOrEqual(4.5);
    }
  }
});
