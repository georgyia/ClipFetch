import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { useSelection } from "../lib/useSelection";
import { SelectionBar } from "./SelectionBar";

function renderBar(selection: ReturnType<typeof useSelection>, allIds: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SelectionBar selection={selection} allIds={allIds} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ favorite: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("selection tracks clips by id, not by position", () => {
  const { result } = renderHook(() => useSelection());

  act(() => result.current.setActive(true));
  act(() => result.current.toggle("IG_2", true));
  act(() => result.current.toggle("IG_5", true));

  expect(result.current.count).toBe(2);
  expect(result.current.has("IG_2")).toBe(true);
  expect(result.current.has("IG_9")).toBe(false);

  act(() => result.current.toggle("IG_2", false));
  expect(result.current.ids).toEqual(["IG_5"]);
});

test("leaving selection mode clears the set, so nothing can be acted on unseen", () => {
  const { result } = renderHook(() => useSelection());

  act(() => result.current.setActive(true));
  act(() => result.current.selectAll(["A", "B", "C"]));
  expect(result.current.count).toBe(3);

  act(() => result.current.setActive(false));
  expect(result.current.active).toBe(false);
  expect(result.current.count).toBe(0);
});

test("the bar renders nothing until selection mode is on", () => {
  const { result } = renderHook(() => useSelection());
  const { container } = renderBar(result.current, ["A"]);
  expect(container).toBeEmptyDOMElement();
});

test("bulk favorite issues one write per selected clip and reports the count", async () => {
  const { result } = renderHook(() => useSelection());
  act(() => result.current.setActive(true));
  act(() => result.current.toggle("A", true));
  act(() => result.current.toggle("B", true));

  renderBar(result.current, ["A", "B", "C"]);
  expect(screen.getByText("2 selected")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Favorite" }));

  await waitFor(() => {
    const puts = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([, init]) => init?.method === "PUT");
    expect(puts).toHaveLength(2);
  });
});

test("actions that need a selection are disabled while none is made", () => {
  const { result } = renderHook(() => useSelection());
  act(() => result.current.setActive(true));

  renderBar(result.current, ["A", "B"]);
  expect(screen.getByRole("button", { name: "Favorite" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Add to collection" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Select all" })).toBeEnabled();
});

test("bulk add opens the collection picker for the whole selection", async () => {
  vi.mocked(globalThis.fetch).mockImplementation(
    async () =>
      new Response(JSON.stringify({ collections: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  const { result } = renderHook(() => useSelection());
  act(() => result.current.setActive(true));
  act(() => result.current.toggle("A", true));
  act(() => result.current.toggle("B", true));

  renderBar(result.current, ["A", "B", "C"]);
  fireEvent.click(screen.getByRole("button", { name: "Add to collection" }));

  expect(
    await screen.findByRole("heading", { name: "Add 2 clips to a collection" }),
  ).toBeInTheDocument();
});
