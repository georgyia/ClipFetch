import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipCard, type ClipCardProps } from "./ClipCard";

/**
 * The card now carries a real FavoriteButton, which reads the favorite flag through React Query —
 * so an isolated card needs a client, exactly as it has one inside the app.
 */
function renderCard(clip = makeClip(), props: Partial<ClipCardProps> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ClipCard clip={clip} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("links to the clip detail route with an accessible label", () => {
  renderCard(makeClip({ caption: "One-pan pasta" }));
  const link = screen.getByRole("link", { name: "One-pan pasta" });
  expect(link).toHaveAttribute("href", "/clip/IG_COOK1");
});

test("renders duration and a lazy poster", () => {
  const { container } = renderCard(makeClip({ duration_seconds: 75 }));
  expect(screen.getByText("1:15")).toBeInTheDocument();
  // The poster is decorative (empty alt), so query it directly rather than by role.
  const poster = container.querySelector("img");
  expect(poster).toHaveAttribute("loading", "lazy");
  expect(poster).toHaveAttribute("src", "/api/v1/clips/IG_COOK1/poster");
});

test("marks unavailable media", () => {
  renderCard(makeClip({ available: false }));
  expect(screen.getByText("Media unavailable")).toBeInTheDocument();
});

test("falls back to author when there is no caption", () => {
  renderCard(makeClip({ caption: null, author: "chef" }));
  expect(screen.getByRole("link", { name: "chef" })).toBeInTheDocument();
});

test("plays an inline preview after dwelling on the card, and stops on leave", async () => {
  renderCard(makeClip({ caption: "Hover me" }));
  const link = screen.getByRole("link", { name: "Hover me" });
  expect(screen.queryByTestId("hover-preview")).not.toBeInTheDocument();

  fireEvent.pointerEnter(link);
  const preview = await screen.findByTestId("hover-preview");
  expect(preview).toHaveAttribute("src", "/api/v1/clips/IG_COOK1/media");
  expect(preview).toHaveAttribute("poster", "/api/v1/clips/IG_COOK1/poster");

  fireEvent.pointerLeave(link);
  await waitFor(() => expect(screen.queryByTestId("hover-preview")).not.toBeInTheDocument());
});

test("never previews unavailable media", async () => {
  renderCard(makeClip({ caption: "No media", available: false }));
  fireEvent.pointerEnter(screen.getByRole("link", { name: "No media" }));
  // Give the dwell timer time to elapse; the preview must still not appear.
  await new Promise((resolve) => setTimeout(resolve, 700));
  expect(screen.queryByTestId("hover-preview")).not.toBeInTheDocument();
});

test("offers Favorite directly on the card, without opening the clip", () => {
  renderCard();
  expect(screen.getByRole("button", { name: /Favorite/ })).toBeInTheDocument();
});

test("offers Add to collection on the card, and opens the picker in place", async () => {
  renderCard(makeClip({ caption: "One-pan pasta" }));
  const add = screen.getByRole("button", { name: "Add One-pan pasta to a collection" });

  fireEvent.click(add);
  expect(
    await screen.findByRole("heading", { name: "Add 1 clip to a collection" }),
  ).toBeInTheDocument();
});

test("a surface can contribute its own card control, e.g. remove from a collection", () => {
  renderCard(makeClip(), {
    action: <button type="button">Remove from keepers</button>,
  });
  expect(screen.getByRole("button", { name: "Remove from keepers" })).toBeInTheDocument();
});

test("shows no checkbox until the grid enters selection mode", () => {
  renderCard();
  expect(screen.queryByRole("checkbox")).toBeNull();
});

test("a selectable card exposes a labelled checkbox and reports changes", () => {
  const changes: boolean[] = [];
  renderCard(makeClip({ caption: "One-pan pasta" }), {
    selectable: true,
    selected: false,
    onSelectChange: (next) => changes.push(next),
  });

  const box = screen.getByRole("checkbox", { name: "Select One-pan pasta" });
  expect(box).not.toBeChecked();

  fireEvent.click(box);
  expect(changes).toEqual([true]);
});

test("the clip link and the card controls are separate tab stops", () => {
  renderCard(makeClip({ caption: "One-pan pasta" }), { selectable: true });
  // A <button> nested inside an <a> would be invalid and unreachable; both must be real siblings.
  expect(screen.getByRole("link", { name: "One-pan pasta" })).toBeInTheDocument();
  expect(screen.getByRole("checkbox")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Favorite/ })).toBeInTheDocument();
});
