import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";

const DIAGNOSTICS = {
  app_version: "0.2.0",
  generated_at: "2026-01-01T00:00:00Z",
  schema: { appstate: 3, catalog: 9 },
  worker: { state: "not_configured" },
  capabilities: { semantic: { available: false, reason: "fastembed missing" } },
  platforms: [
    { name: "Instagram", support: "full" },
    { name: "TikTok", support: "experimental" },
    { name: "YouTube", support: "unavailable" },
  ],
  libraries: { count: 1, active: { health: "ready", clip_count: 12 } },
  jobs: { queued: 2, running: 0, succeeded: 5, failed: 1, cancelled: 0 },
};

let clipboardText = "";

beforeEach(() => {
  clipboardText = "";
  vi.stubGlobal("navigator", {
    clipboard: {
      writeText: vi.fn(async (text: string) => {
        clipboardText = text;
      }),
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(DIAGNOSTICS), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

test("renders versions, platforms, and job counts", async () => {
  renderPage();
  expect(await screen.findByText("0.2.0")).toBeInTheDocument();
  expect(screen.getByText("Instagram")).toBeInTheDocument();
  expect(screen.getByText("experimental")).toBeInTheDocument();
  expect(screen.getByText("ready")).toBeInTheDocument();
});

test("copies a support bundle to the clipboard", async () => {
  renderPage();
  await screen.findByText("0.2.0");
  fireEvent.click(screen.getByRole("button", { name: "Copy support bundle" }));
  await waitFor(() => expect(screen.getByText(/copied to clipboard/i)).toBeInTheDocument());
  expect(JSON.parse(clipboardText)).toMatchObject({ app_version: "0.2.0" });
});
