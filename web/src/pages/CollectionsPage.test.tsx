import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { CollectionsPage } from "./CollectionsPage";

let collections: Array<{ id: string; filters: Record<string, unknown>; clip_count: number }>;

beforeEach(() => {
  collections = [{ id: "popular", filters: { min_likes: 1000000 }, clip_count: 2 }];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/topics")) {
        return new Response(JSON.stringify({ topics: [] }), { status: 200 });
      }
      if (url.endsWith("/collections") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        const created = { id: body.name, filters: body.filters, clip_count: 0 };
        collections.push(created);
        return new Response(JSON.stringify(created), { status: 201 });
      }
      if (method === "DELETE") {
        const id = url.split("/").pop() ?? "";
        collections = collections.filter((item) => item.id !== decodeURIComponent(id));
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify({ collections }), { status: 200 });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CollectionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists collections and creates a new one", async () => {
  renderPage();
  expect(await screen.findByRole("link", { name: "Popular" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "big-hits" } });
  fireEvent.click(screen.getByRole("button", { name: "Create" }));

  expect(await screen.findByRole("link", { name: "Big Hits" })).toBeInTheDocument();
});

test("deletes a collection", async () => {
  renderPage();
  const del = await screen.findAllByRole("button", { name: "Delete" });
  fireEvent.click(del[0]);
  await waitFor(() =>
    expect(screen.queryByRole("link", { name: "Popular" })).not.toBeInTheDocument(),
  );
});
