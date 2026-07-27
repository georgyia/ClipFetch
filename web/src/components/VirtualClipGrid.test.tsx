import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipGrid } from "./ClipGrid";
import { GRID_GAP, GRID_MIN_COLUMN, GRID_WIDE_BREAKPOINT, gridGeometry } from "./VirtualClipGrid";

function manyClips(count: number) {
  return Array.from({ length: count }, (_, index) =>
    makeClip({ id: `IG_${index}`, caption: `Clip ${index}` }),
  );
}

test("column count inverts the CSS auto-fill formula", () => {
  // 1200px wide, 168px minimum, 20px gap → floor((1200 + 20) / 188) = 6 columns.
  expect(gridGeometry(1200, 1440).columns).toBe(6);
  // A narrow viewport uses the smaller minimum and gap: floor((360 + 16) / 156) = 2.
  expect(gridGeometry(360, 400).columns).toBe(2);
});

test("never reports fewer than one column, however narrow the container", () => {
  expect(gridGeometry(40, 320).columns).toBe(1);
  expect(gridGeometry(0, 320).columns).toBe(1);
});

test("row height follows the 9:16 card plus its meta block", () => {
  const { columns, rowHeight, gap } = gridGeometry(1200, 1440);
  const columnWidth = (1200 - gap * (columns - 1)) / columns;
  // Taller than the poster alone, because the caption and subtitle sit under it.
  expect(rowHeight).toBeGreaterThan(columnWidth * (16 / 9));
});

/*
 * The virtualizer duplicates the grid's column geometry because it has to compute row heights in
 * JS, while the CSS remains the source of truth for layout. This asserts the two have not drifted:
 * if someone changes the minmax() or gap in ClipGrid.module.css, this fails rather than silently
 * mispositioning every row.
 */
test("the JS geometry constants still match ClipGrid.module.css", () => {
  // Paths are relative to the Vitest root, which is the web/ package directory.
  const css = readFileSync(resolve("src/components/ClipGrid.module.css"), "utf8");
  expect(css).toContain(`minmax(${GRID_MIN_COLUMN.narrow}px, 1fr)`);
  expect(css).toContain(`minmax(${GRID_MIN_COLUMN.wide}px, 1fr)`);
  expect(css).toContain(`min-width: ${GRID_WIDE_BREAKPOINT}px`);
  // The gaps are token references, so check the tokens resolve to the pixel values assumed here.
  const tokens = readFileSync(resolve("src/styles/tokens.css"), "utf8");
  expect(tokens).toContain(`--space-5: ${GRID_GAP.narrow}px`);
  expect(tokens).toContain(`--space-6: ${GRID_GAP.wide}px`);
});

test("small result sets render every card in a plain grid", () => {
  render(
    <MemoryRouter>
      <ClipGrid items={manyClips(12)} label="Results" />
    </MemoryRouter>,
  );
  expect(screen.getAllByRole("link")).toHaveLength(12);
});

test("large result sets switch to a windowed grid instead of rendering everything", () => {
  render(
    <MemoryRouter>
      <ClipGrid items={manyClips(500)} label="Results" />
    </MemoryRouter>,
  );
  // The list is still one labelled region for assistive tech...
  expect(screen.getByLabelText("Results")).toBeInTheDocument();
  // ...but nowhere near 500 cards exist in the DOM.
  expect(screen.getAllByRole("link").length).toBeLessThan(500);
});
