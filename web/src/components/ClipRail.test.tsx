import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipRail } from "./ClipRail";

const ITEMS = [
  makeClip({ id: "A", caption: "Alpha" }),
  makeClip({ id: "B", caption: "Beta" }),
  makeClip({ id: "C", caption: "Gamma" }),
];

function renderRail() {
  return render(
    <MemoryRouter>
      <ClipRail title="Recently Added" items={ITEMS} seeAllTo="/library" />
    </MemoryRouter>,
  );
}

test("renders a titled rail with a see-all link", () => {
  renderRail();
  expect(screen.getByRole("region", { name: "Recently Added" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See all →" })).toHaveAttribute("href", "/library");
});

test("arrow keys move focus between cards", () => {
  renderRail();
  const first = screen.getByRole("link", { name: "Alpha" });
  const second = screen.getByRole("link", { name: "Beta" });
  first.focus();
  fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(second).toHaveFocus();
  fireEvent.keyDown(second, { key: "ArrowLeft" });
  expect(first).toHaveFocus();
});

test("renders nothing when empty", () => {
  const { container } = render(
    <MemoryRouter>
      <ClipRail title="Empty" items={[]} />
    </MemoryRouter>,
  );
  expect(container).toBeEmptyDOMElement();
});
