import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { makeClip } from "../test/fixtures";
import { ClipCard } from "./ClipCard";

function renderCard(clip = makeClip()) {
  return render(
    <MemoryRouter>
      <ClipCard clip={clip} />
    </MemoryRouter>,
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
