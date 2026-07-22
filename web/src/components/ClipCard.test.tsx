import { render, screen } from "@testing-library/react";
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
