import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast("Saved!", { variant: "success" })}>
      go
    </button>
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

function renderWithProvider() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>,
  );
}

test("shows a toast on demand and announces it politely", () => {
  renderWithProvider();
  act(() => {
    fireEvent.click(screen.getByRole("button", { name: "go" }));
  });
  expect(screen.getByText("Saved!")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
});

test("auto-dismisses after the timeout", () => {
  renderWithProvider();
  act(() => {
    fireEvent.click(screen.getByRole("button", { name: "go" }));
  });
  expect(screen.getByText("Saved!")).toBeInTheDocument();
  act(() => {
    vi.advanceTimersByTime(4000);
  });
  expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
});

test("can be dismissed manually", () => {
  renderWithProvider();
  act(() => {
    fireEvent.click(screen.getByRole("button", { name: "go" }));
  });
  act(() => {
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
  });
  expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
});

test("useToast outside a provider is a no-op and does not throw", () => {
  // Renders Trigger without a provider; clicking must not crash.
  render(<Trigger />);
  expect(() => fireEvent.click(screen.getByRole("button", { name: "go" }))).not.toThrow();
});
