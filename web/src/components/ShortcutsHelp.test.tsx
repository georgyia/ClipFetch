import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { ShortcutsHelp } from "./ShortcutsHelp";

afterEach(() => {
  // Ensure the global keydown listener from one test doesn't leak into the next.
  fireEvent.keyDown(window, { key: "Escape" });
});

test("opens the shortcuts dialog on ? and lists player keys", () => {
  render(<ShortcutsHelp />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  fireEvent.keyDown(window, { key: "?" });
  const dialog = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
  expect(dialog).toBeInTheDocument();
  expect(screen.getByText("Play / pause")).toBeInTheDocument();
  expect(screen.getByText("Toggle shuffle")).toBeInTheDocument();
});

test("ignores ? while typing in a field", () => {
  render(
    <>
      <input aria-label="query" />
      <ShortcutsHelp />
    </>,
  );
  const input = screen.getByLabelText("query");
  input.focus();
  fireEvent.keyDown(input, { key: "?" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
