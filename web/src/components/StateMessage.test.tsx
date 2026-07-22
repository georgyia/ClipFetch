import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { QualityBadge } from "./QualityBadge";
import { TopicChip } from "./TopicChip";

test("empty state renders a heading, description, and action", () => {
  render(
    <EmptyState
      title="No clips yet"
      description="Download some reels to get started."
      action={<Button>Add downloads</Button>}
    />,
  );
  expect(screen.getByRole("heading", { name: "No clips yet" })).toBeInTheDocument();
  expect(screen.getByText(/Download some reels/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add downloads" })).toBeInTheDocument();
});

test("error state is announced as an alert", () => {
  render(<ErrorState title="Something failed" description="Try again." />);
  expect(screen.getByRole("alert")).toHaveTextContent("Something failed");
});

test("badges render human labels", () => {
  const { rerender } = render(<QualityBadge tier="full_hd" />);
  expect(screen.getByText("Full HD")).toBeInTheDocument();
  rerender(<QualityBadge tier="mystery" />);
  expect(screen.getByText("Unknown")).toBeInTheDocument();

  render(<TopicChip label="health-and-fitness" />);
  expect(screen.getByText("Health And Fitness")).toBeInTheDocument();
});
