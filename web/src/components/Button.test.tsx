import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { Button } from "./Button";

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
