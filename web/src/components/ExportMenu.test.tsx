import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ExportMenu } from "./ExportMenu";

test("offers both formats as real downloads from the given view", () => {
  render(<ExportMenu path="/api/v1/collections/keepers/export" count={12} />);

  const playlist = screen.getByRole("link", { name: /Playlist/ });
  const manifest = screen.getByRole("link", { name: /Manifest/ });

  // Plain links, so the browser owns the download: a real Save dialog, no blob in JS memory.
  expect(playlist).toHaveAttribute("href", "/api/v1/collections/keepers/export?format=m3u");
  expect(manifest).toHaveAttribute("href", "/api/v1/collections/keepers/export?format=json");
  expect(playlist).toHaveAttribute("download");
});

test("appends the format to a path that already carries filters", () => {
  render(<ExportMenu path="/api/v1/clips/export?platform=tiktok&sort=likes" count={3} />);
  expect(screen.getByRole("link", { name: /Playlist/ })).toHaveAttribute(
    "href",
    "/api/v1/clips/export?platform=tiktok&sort=likes&format=m3u",
  );
});

test("names the size of the set before you download it", () => {
  render(<ExportMenu path="/api/v1/clips/export" count={1} />);
  expect(screen.getByText("1 clip in this view")).toBeInTheDocument();
});
