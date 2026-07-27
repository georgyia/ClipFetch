import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { Button } from "./Button";
import { Icons } from "./icons";

test("renders an accessible button and fires onClick", () => {
  const onClick = vi.fn();
  render(<Button onClick={onClick}>Play</Button>);
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  expect(onClick).toHaveBeenCalledOnce();
});

test("defaults to type=button and can be disabled", () => {
  const { rerender } = render(<Button>Go</Button>);
  expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  rerender(
    <Button disabled variant="primary">
      Go
    </Button>,
  );
  expect(screen.getByRole("button")).toBeDisabled();
});

test("a leading icon does not pollute the accessible name", () => {
  render(
    <Button icon={Icons.play} variant="primary">
      Play all
    </Button>,
  );
  expect(screen.getByRole("button", { name: "Play all" })).toBeInTheDocument();
});

test("loading blocks input, marks the button busy, and keeps the label", () => {
  const onClick = vi.fn();
  render(
    <Button loading onClick={onClick}>
      Rescan
    </Button>,
  );
  const button = screen.getByRole("button", { name: "Rescan" });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute("aria-busy", "true");
  fireEvent.click(button);
  expect(onClick).not.toHaveBeenCalled();
});

test("an icon-only button takes its name from aria-label", () => {
  render(<Button iconOnly icon={Icons.close} aria-label="Close player" />);
  expect(screen.getByRole("button", { name: "Close player" })).toBeInTheDocument();
});
