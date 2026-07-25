import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { makeClip } from "../test/fixtures";
import { Hero } from "./Hero";

function renderHero(clip = makeClip()) {
  return render(
    <MemoryRouter>
      <Hero clip={clip} />
    </MemoryRouter>,
  );
}

test("shows the featured title and a Play call to action", () => {
  renderHero(makeClip({ caption: "Big night" }));
  expect(screen.getByRole("heading", { name: "Big night" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Play/ })).toHaveAttribute("href", "/clip/IG_COOK1");
});

test("comes to life with a muted autoplay preview", async () => {
  renderHero(makeClip({ caption: "Billboard" }));
  const preview = await screen.findByTestId("hero-preview", undefined, { timeout: 2500 });
  expect(preview.tagName).toBe("VIDEO");
  expect(preview).toHaveAttribute("src", "/api/v1/clips/IG_COOK1/media");
});

test("stays a still when the media is unavailable", async () => {
  renderHero(makeClip({ available: false }));
  await new Promise((resolve) => setTimeout(resolve, 1400));
  expect(screen.queryByTestId("hero-preview")).not.toBeInTheDocument();
});
