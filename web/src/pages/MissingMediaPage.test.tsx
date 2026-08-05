import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { makeClip } from "../test/fixtures";
import { MissingMediaPage } from "./MissingMediaPage";

let missing: unknown[];

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  missing = [
    {
      ...makeClip({ id: "GONE1", caption: "Vanished clip", available: false }),
      relative_path: "instagram/GONE1.mp4",
      file_size_bytes: 2048,
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/maintenance/missing/forget")) {
        const body = JSON.parse(String(init?.body));
        missing = [];
        return json({ forgotten: body.clip_ids, kept: [], unknown: [] });
      }
      if (url.includes("/maintenance/missing")) {
        return json({ items: missing, total: missing.length, next_offset: null });
      }
      if (url.includes("/bootstrap")) {
        return json({ active_library: { id: "lib-1", display_name: "Reels" } });
      }
      return json({});
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
        <MissingMediaPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("lists the file that went missing, so you know what to look for", async () => {
  renderPage();
  expect(await screen.findByText("Vanished clip")).toBeInTheDocument();
  expect(screen.getByText("instagram/GONE1.mp4")).toBeInTheDocument();
});

test("forgetting is confirmed first, and the confirmation says no file is deleted", async () => {
  renderPage();
  await screen.findByText("Vanished clip");

  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: /Forget 1 selected/ }));

  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveTextContent(/No file is deleted/i);
  expect(dialog).toHaveTextContent(/re-indexing the library restores the clip/i);
});

test("confirming forgets exactly the selected records", async () => {
  renderPage();
  await screen.findByText("Vanished clip");

  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: /Forget 1 selected/ }));
  fireEvent.click(screen.getByRole("button", { name: "Forget them" }));

  await waitFor(() => {
    const posts = vi
      .mocked(globalThis.fetch)
      .mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ clip_ids: ["GONE1"] });
  });
});

test("nothing can be forgotten until something is selected", async () => {
  renderPage();
  await screen.findByText("Vanished clip");
  expect(screen.getByRole("button", { name: /Forget selected/ })).toBeDisabled();
});

test("a healthy library says so rather than showing an empty table", async () => {
  missing = [];
  renderPage();
  expect(await screen.findByText(/Every clip's file is where it should be/)).toBeInTheDocument();
});
