import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { RouteAnnouncer, titleForPath } from "./RouteAnnouncer";

test("maps paths to page titles", () => {
  expect(titleForPath("/")).toBe("Home");
  expect(titleForPath("/explore")).toBe("Explore");
  expect(titleForPath("/library/favorites")).toBe("Favorites");
  expect(titleForPath("/collections/big-hits")).toBe("Collection");
  expect(titleForPath("/clip/IG_1")).toBe("Clip details");
  expect(titleForPath("/watch/IG_1")).toBe("Player");
});

test("announces the page and sets the document title on navigation", () => {
  render(
    <MemoryRouter initialEntries={["/explore"]}>
      <RouteAnnouncer />
    </MemoryRouter>,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Explore page");
  expect(document.title).toBe("Explore · ClipFetch Watch");
});
