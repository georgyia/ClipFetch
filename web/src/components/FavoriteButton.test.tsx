import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { FavoriteButton } from "./FavoriteButton";

let favorited = false;

beforeEach(() => {
  favorited = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method;
      if (method === "PUT") {
        favorited = true;
      } else if (method === "DELETE") {
        favorited = false;
        return new Response(null, { status: 204 });
      }
      // GET reflects the current server state.
      return new Response(JSON.stringify({ favorite: favorited }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderButton() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FavoriteButton clipId="IG_COOK1" />
    </QueryClientProvider>,
  );
}

test("optimistically flips to favorited and issues a PUT", async () => {
  renderButton();
  const button = await screen.findByRole("button", { name: /Favorite/ });
  expect(button).toHaveAttribute("aria-pressed", "false");

  fireEvent.click(button);
  // Optimistic: reflects the new state before the request settles.
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /Favorited/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );

  const fetchMock = vi.mocked(globalThis.fetch);
  const put = fetchMock.mock.calls.find(
    ([url, init]) => String(url).includes("/favorite") && init?.method === "PUT",
  );
  expect(put).toBeDefined();
});
