import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Badge } from "./Badge";
import { Chip } from "./Chip";
import { Icon } from "./Icon";
import { Icons } from "./icons";

test("icons are decorative by default and hidden from assistive tech", () => {
  const { container } = render(<Icon icon={Icons.play} />);
  const svg = container.querySelector("svg");
  expect(svg).toHaveAttribute("aria-hidden", "true");
  // No accessible name is exposed, so an adjacent text label is not announced twice.
  expect(screen.queryByRole("img")).toBeNull();
});

test("a labelled icon becomes an img with that name", () => {
  render(<Icon icon={Icons.favorite} label="Favorited" />);
  expect(screen.getByRole("img", { name: "Favorited" })).toBeInTheDocument();
});

test("icon size maps to the optical ramp rather than raw pixels", () => {
  const { container } = render(<Icon icon={Icons.play} size="xl" />);
  expect(container.querySelector("svg")).toHaveAttribute("width", "28");
});

test("badges render their tone and stay non-interactive", () => {
  render(<Badge tone="success">Full HD</Badge>);
  const badge = screen.getByText("Full HD");
  expect(badge.tagName).toBe("SPAN");
  expect(screen.queryByRole("button")).toBeNull();
});

test("a toggle chip exposes pressed state", () => {
  render(
    <Chip selected onToggle={() => {}}>
      Cooking
    </Chip>,
  );
  expect(screen.getByRole("button", { name: /Cooking/ })).toHaveAttribute("aria-pressed", "true");
});

test("a removable chip exposes the dismiss control on its own tab stop", () => {
  render(
    <Chip onRemove={() => {}} removeLabel="Remove topic filter">
      Cooking
    </Chip>,
  );
  expect(screen.getByRole("button", { name: "Remove topic filter" })).toBeInTheDocument();
});
