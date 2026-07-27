import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { SkeletonClipDetail, SkeletonGrid, SkeletonHome, SkeletonList } from "./Skeletons";
import { Icons } from "./icons";

test("a skeleton announces loading once, not once per placeholder", () => {
  render(<SkeletonGrid count={12} label="Loading favorites" />);
  const statuses = screen.getAllByRole("status");
  expect(statuses).toHaveLength(1);
  expect(statuses[0]).toHaveTextContent("Loading favorites");
});

test("placeholders themselves are hidden from assistive tech", () => {
  const { container } = render(<SkeletonList rows={3} />);
  const placeholders = container.querySelectorAll('[aria-hidden="true"]');
  expect(placeholders.length).toBeGreaterThan(0);
});

test("the grid skeleton renders the requested number of cards", () => {
  const { container } = render(<SkeletonGrid count={5} />);
  // Each card is a poster plus two text lines.
  expect(container.querySelectorAll("[class*='card']")).toHaveLength(5);
});

test("home and detail skeletons render their distinct shapes", () => {
  const { unmount } = render(<SkeletonHome />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading your library");
  unmount();

  render(<SkeletonClipDetail />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading clip");
});

test("an empty state offers a way forward, not just an explanation", () => {
  render(
    <MemoryRouter>
      <EmptyState
        icon={Icons.downloads}
        title="Your library is empty"
        description="Queue a download to get started."
        action={<Button variant="primary">Add reels</Button>}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: "Your library is empty" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add reels" })).toBeInTheDocument();
});

test("an error state is announced and offers a retry that calls back", async () => {
  let retried = 0;
  render(<ErrorState title="Search failed" description="Try again." onRetry={() => retried++} />);

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("Search failed");

  screen.getByRole("button", { name: "Try again" }).click();
  expect(retried).toBe(1);
});

test("a retrying error state disables its own button so retries cannot stack", () => {
  render(<ErrorState title="Search failed" onRetry={() => {}} retrying />);
  const button = screen.getByRole("button", { name: "Try again" });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute("aria-busy", "true");
});

test("an error state with no retry handler shows no retry button", () => {
  render(<ErrorState title="Nope" description="No recovery available." />);
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
});
