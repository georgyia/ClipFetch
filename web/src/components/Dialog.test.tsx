import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { Button } from "./Button";
import { Dialog } from "./Dialog";

test("does not render when closed", () => {
  render(
    <Dialog open={false} onClose={vi.fn()} title="Delete">
      body
    </Dialog>,
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("exposes an accessible modal labelled by its title and focuses inside", () => {
  render(
    <Dialog open onClose={vi.fn()} title="Delete clip">
      <Button>Confirm</Button>
    </Dialog>,
  );
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(dialog).toHaveAccessibleName("Delete clip");
  // Focus moves to the first focusable control inside the dialog.
  expect(screen.getByRole("button", { name: "Confirm" })).toHaveFocus();
});

test("closes on Escape and via the backdrop", () => {
  const onClose = vi.fn();
  render(
    <Dialog open onClose={onClose} title="Delete clip">
      <Button>Confirm</Button>
    </Dialog>,
  );
  fireEvent.keyDown(document, { key: "Escape" });
  expect(onClose).toHaveBeenCalledOnce();

  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(onClose).toHaveBeenCalledTimes(2);
});
