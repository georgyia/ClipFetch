import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";
import { resetOverlays } from "../lib/overlays";
import { useGlobalShortcuts } from "../lib/useGlobalShortcuts";
import { ShortcutsHelp } from "./ShortcutsHelp";

/**
 * The "?" binding lives in useGlobalShortcuts (App mounts it once) rather than inside the dialog,
 * so the harness mounts both — that is the real wiring.
 */
function Harness({ withInput = false }: { withInput?: boolean }) {
  useGlobalShortcuts();
  return (
    <>
      {withInput ? <input aria-label="query" /> : null}
      <ShortcutsHelp />
    </>
  );
}

beforeEach(() => {
  resetOverlays();
});

afterEach(() => {
  resetOverlays();
});

test("opens the shortcuts dialog on ? and lists player keys", () => {
  render(<Harness />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  fireEvent.keyDown(window, { key: "?" });
  expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  expect(screen.getByText("Play / pause")).toBeInTheDocument();
  expect(screen.getByText("Toggle shuffle")).toBeInTheDocument();
});

test("documents the command palette alongside the player keys", () => {
  render(<Harness />);
  fireEvent.keyDown(window, { key: "?" });
  expect(screen.getByText("Open the command palette")).toBeInTheDocument();
  expect(screen.getByText("Run the highlighted command")).toBeInTheDocument();
});

test("ignores ? while typing in a field", () => {
  render(<Harness withInput />);
  const input = screen.getByLabelText("query");
  input.focus();
  fireEvent.keyDown(input, { key: "?" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
