import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { resetOverlays } from "../lib/overlays";
import { useGlobalShortcuts } from "../lib/useGlobalShortcuts";
import { CommandPalette } from "./CommandPalette";
import { ShortcutsHelp } from "./ShortcutsHelp";

/** Renders the palette plus a probe that reports the current URL, so we can assert navigation. */
function Harness() {
  useGlobalShortcuts();
  return (
    <>
      <CommandPalette />
      <ShortcutsHelp />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </>
  );
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

function renderPalette() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <Harness />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  resetOverlays();
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ topics: [], collections: [], items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  resetOverlays();
  vi.unstubAllGlobals();
});

function openWithShortcut() {
  fireEvent.keyDown(window, { key: "k", metaKey: true });
}

test("⌘K opens the palette from anywhere", async () => {
  renderPalette();
  expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull();

  openWithShortcut();
  expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
  expect(screen.getByRole("combobox")).toHaveFocus();
});

test("Ctrl+K works too, for non-Mac keyboards", async () => {
  renderPalette();
  fireEvent.keyDown(window, { key: "k", ctrlKey: true });
  expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
});

test("typing filters the command list", async () => {
  renderPalette();
  openWithShortcut();
  const input = screen.getByRole("combobox");

  expect(screen.getByRole("option", { name: /Explore/ })).toBeInTheDocument();
  fireEvent.change(input, { target: { value: "downl" } });

  await waitFor(() => expect(screen.queryByRole("option", { name: /Explore/ })).toBeNull());
  expect(screen.getByRole("option", { name: /Downloads/ })).toBeInTheDocument();
});

test("arrow keys move the selection and Enter runs it", async () => {
  renderPalette();
  openWithShortcut();
  const input = screen.getByRole("combobox");

  // First option is Home; one step down lands on Explore.
  fireEvent.keyDown(input, { key: "ArrowDown" });
  const options = screen.getAllByRole("option");
  expect(options[1]).toHaveAttribute("aria-selected", "true");
  expect(options[0]).toHaveAttribute("aria-selected", "false");

  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/explore"));
  // Running a command closes the palette.
  expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull();
});

test("a free-text query offers a search escape hatch that routes to /search", async () => {
  renderPalette();
  openWithShortcut();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "pasta" } });

  const search = await screen.findByRole("option", { name: /Search for/ });
  fireEvent.click(search);

  await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/search?q=pasta"));
});

test("Escape closes the palette", async () => {
  renderPalette();
  openWithShortcut();
  await screen.findByRole("dialog", { name: "Command palette" });

  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull());
});

test("the palette can open the shortcuts sheet", async () => {
  renderPalette();
  openWithShortcut();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "keyboard" } });

  fireEvent.click(await screen.findByRole("option", { name: /Show keyboard shortcuts/ }));
  expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
});

test("aria-activedescendant tracks the highlighted option", () => {
  renderPalette();
  openWithShortcut();
  const input = screen.getByRole("combobox");

  const initial = input.getAttribute("aria-activedescendant");
  expect(initial).toBeTruthy();
  expect(document.getElementById(initial as string)).toHaveAttribute("aria-selected", "true");

  fireEvent.keyDown(input, { key: "ArrowDown" });
  const next = input.getAttribute("aria-activedescendant");
  expect(next).not.toBe(initial);
  expect(document.getElementById(next as string)).toHaveAttribute("aria-selected", "true");
});

test("'?' opens the shortcuts sheet but is ignored while typing in the palette", async () => {
  renderPalette();
  fireEvent.keyDown(window, { key: "?" });
  expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();

  fireEvent.keyDown(window, { key: "?" });
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).toBeNull(),
  );

  // Inside a text field, "?" must type a character rather than opening a dialog.
  openWithShortcut();
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "?" });
  expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).toBeNull();
});
