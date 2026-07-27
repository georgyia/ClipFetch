import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipRail } from "./ClipRail";

const ITEMS = [
  makeClip({ id: "A", caption: "Alpha" }),
  makeClip({ id: "B", caption: "Beta" }),
  makeClip({ id: "C", caption: "Gamma" }),
];

/** Cards carry a FavoriteButton, so even an isolated rail needs a query client. */
function renderRail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ClipRail title="Recently Added" items={ITEMS} seeAllTo="/library" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders a titled rail with a see-all link", () => {
  renderRail();
  expect(screen.getByRole("region", { name: "Recently Added" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See all" })).toHaveAttribute("href", "/library");
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

test("paging chevron scrolls the track a page at a time", () => {
  renderRail();
  const track = screen.getByRole("list");
  const scrollBy = vi.fn();
  track.scrollBy = scrollBy;
  fireEvent.click(screen.getByRole("button", { name: "Scroll Recently Added forward" }));
  expect(scrollBy).toHaveBeenCalledWith(expect.objectContaining({ behavior: "smooth" }));
});

test("renders nothing when empty", () => {
  const { container } = render(
    <MemoryRouter>
      <ClipRail title="Empty" items={[]} />
    </MemoryRouter>,
  );
  expect(container).toBeEmptyDOMElement();
});
